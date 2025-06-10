## Core functionalities for Battery-Free Nodes
## Supports multiple protocols ('ours', 'baseline') selected at instantiation.
## Takes in clock tick, energy, computes energy level, decides actions.

import random
import math
from enum import Enum
import numpy as np
from interface import Subscriber
import logging

# --- Enums ---
class ACTION(Enum):
    SLEEP = 0
    ADVERTISE = 1
    SCAN = 2 # Used only by 'ours' protocol

class STATE(Enum):
    ON = 1
    OFF = 0

class RADIO_STATE(Enum):
    SUCCESS = 1
    FAILURE = 0

# RUN_TYPE can potentially override 'ours' protocol behavior for testing
class RUN_TYPE(Enum):
    SCANNING = 0    # Force scanning (if protocol='ours')
    ADVERTISING = 1 # Force advertising (if protocol='ours')
    NORMAL = 2      # Standard behavior for the selected protocol

class Node():
    # Added protocol_type parameter
    # MODIFIED: Added 'rng' parameter to __init__ signature
    def __init__ (self, id, energy_harvester, clock, radio, offset, alpha, capacitance, von, voff, eadv, escan, nominal_time_period, protocol_type, rng, run_time = 100, runtype= RUN_TYPE.NORMAL, log_level=logging.INFO):
        # --- Core Attributes ---
        self.id = id
        self.energy_harvester = energy_harvester
        self.clock_subscriber = Subscriber(f"clock_node_{id}", clock) # Unique subscriber topic
        self.radio = radio
        self.protocol_type = protocol_type # Store the protocol type ('ours' or 'baseline')
        self.runtype = runtype # Store runtype for potential overrides
        self.rng = rng # Store the random number generator instance

        # --- Energy Parameters ---
        self.capacitance = capacitance
        self.von = von
        self.voff = voff
        self.eadv = eadv
        self.esleep = 10.5e-9 # Assuming constant sleep cost

        # --- Timing Parameters ---
        self.nominal_time_period = nominal_time_period
        self.run_time = run_time # Max simulation cycles (used?) - seems unused currently
        self.ASN = 0 # Absolute Slot Number

        # --- State Variables ---
        self.state = STATE.OFF
        self.energy_level = 0 # Start discharged
        self.action = ACTION.SLEEP
        self.done = False # Flag if discovered by Node 0 (set externally)
        self.ran_once = False # Flag for reset logic

        # --- Logging ---
        self.logger = logging.getLogger(f"Node_{id}_{protocol_type}") # Include protocol in logger name
        self.logger.setLevel(log_level)
        self.logger.disabled = True # Control logging verbosity

        # --- Metrics ---
        self.metrics = {}
        self.metrics["adv_sent"] = 0
        self.metrics["adv_success"] = 0
        # Initialize protocol-specific metrics
        if self.protocol_type == 'ours':
            self.metrics["scan_sent"] = 0
            self.metrics["scan_success"] = 0
        # Baseline doesn't scan

        # --- Protocol-Specific Attributes ---
        if self.protocol_type == 'ours':
            self.alpha = alpha # Probability of choosing advertise
            self.escan = escan # Energy cost for scanning
            self.offset = offset # Preferred advertising slot
            self.channel_map = np.zeros(nominal_time_period) # History of scan successes
            # Calculate number of scans possible with one charge cycle's energy gain (approx)
            # Note: This calculation might be approximate. Consider refining if needed.
            energy_gain_approx = 0.5 * self.capacitance * (self.von**2 - self.voff**2)
            self.n_scans_per_charge = max(1, int(energy_gain_approx / self.escan)) if self.escan > 0 else 1 # Number of scans to perform per cycle
            self.scans_remaining_this_cycle = 0 # Counter for scans
            self.action_decided_this_cycle = False # Flag for alpha decision
            self.next_adv_wakeup = -1 # Scheduled time for next advertisement

        elif self.protocol_type == 'baseline':
            # Baseline specific state
            self.scheduled_advertisement_time = -1 # ASN when the delayed advertisement should happen
            # Baseline ignores alpha, escan, offset, channel_map

        else:
            raise ValueError(f"Unknown protocol_type: {protocol_type} for Node {id}")

        self.logger.info(f"Initialized Node {self.id} with protocol '{self.protocol_type}'")


    def compute_energy_level(self, energy_in):
        """Updates energy level, checks state transitions, and handles reset."""
        self.energy_level = self.energy_level + energy_in

        # Clamp energy level at 0 if it goes negative due to costs
        if self.energy_level < 0:
             self.energy_level = 0

        voltage = math.sqrt(max(0, 2 * self.energy_level / self.capacitance)) # Ensure non-negative voltage calculation

        # Reset logic: If voltage drops below VOFF after being ON at least once
        if voltage < self.voff and self.ran_once:
            self.reset() # Reset state if voltage drops too low

        # State transition logic
        if self.state == STATE.OFF and voltage >= self.von:
            self.state = STATE.ON
            self.logger.debug(f"Node {self.id} turned ON at ASN {self.ASN}")
            # --- Protocol-specific actions on turning ON ---
            if self.protocol_type == 'baseline':
                # Schedule the advertisement after a random delay
                # MODIFIED: Use self.rng instead of random
                delay_slots = self.rng.integers(0, int(0.3 * self.nominal_time_period))
                self.scheduled_advertisement_time = self.ASN + delay_slots
                self.logger.debug(f"Node {self.id} (baseline) scheduled ADV for ASN {self.scheduled_advertisement_time} (delay={delay_slots})")
            elif self.protocol_type == 'ours':
                 # Reset the action decision flag for the new ON cycle
                 self.action_decided_this_cycle = False
                 self.scans_remaining_this_cycle = 0 # Reset scan counter
                 self.next_adv_wakeup = -1 # Reset scheduled advertisement


        elif self.state == STATE.ON and voltage < self.voff:
             # This case is handled by the reset logic above, but ensure state goes OFF
             self.state = STATE.OFF
             self.logger.debug(f"Node {self.id} turned OFF at ASN {self.ASN} due to low voltage")
             # Cancel any scheduled actions if turning off
             if self.protocol_type == 'baseline':
                 self.scheduled_advertisement_time = -1
             elif self.protocol_type == 'ours':
                 self.next_adv_wakeup = -1
                 self.action_decided_this_cycle = False # Reset decision state


    def do_action(self, action_to_do):
        """Instructs the radio based on the chosen action and deducts energy cost."""
        # Only perform actions if ON
        if self.state == STATE.ON:
            cost = 0
            if action_to_do == ACTION.ADVERTISE:
                self.radio.advertise(self.ASN, self.id)
                self.metrics["adv_sent"] += 1
                cost = self.eadv
                self.logger.debug(f"Node {self.id} performing ADV at ASN {self.ASN}")
            elif action_to_do == ACTION.SCAN:
                # Only 'ours' protocol should trigger SCAN
                if self.protocol_type == 'ours':
                    self.radio.scan(self.ASN, self.id)
                    self.metrics["scan_sent"] += 1
                    cost = self.escan
                    self.logger.debug(f"Node {self.id} performing SCAN at ASN {self.ASN}")
                else:
                    self.logger.warning(f"Node {self.id} (baseline) attempted SCAN - ignoring.")
                    action_to_do = ACTION.SLEEP # Default to sleep if SCAN is invalid for protocol
            # Default to SLEEP if action is SLEEP or invalid for the state/protocol
            if action_to_do == ACTION.SLEEP:
                self.radio.sleep()
                # Consume sleep energy only if the node has been ON before
                if self.ran_once:
                     cost = self.esleep

            # Deduct energy cost for the action performed
            if cost > 0:
                self.compute_energy_level(-cost) # Deduct cost via the energy calculation method

        else:
             # Ensure radio is sleeping if node is OFF
             self.radio.sleep()
             # No sleep energy cost if node never turned on or is already OFF


    def build_channel_map(self):
        """Processes radio results based on the protocol."""
        radio_outcome = self.radio.get_message() # Check radio outcome once

        if radio_outcome == RADIO_STATE.SUCCESS and self.state == STATE.ON:
            if self.action == ACTION.ADVERTISE:
                self.logger.info(f"Node {self.id}: ASN {self.ASN}, Advertise Success")
                self.metrics["adv_success"] += 1
                # Node 0 specific logic for 'ours' protocol (reset offset on success)
                if self.protocol_type == 'ours' and self.id == 0:
                     # Reset channel map and offset for the discoverer upon success?
                     # This logic might need review - does Node 0 reset its strategy?
                     # self.channel_map = np.zeros(self.nominal_time_period) # Option: Clear map
                     # MODIFIED: Use self.rng instead of random
                     self.offset = self.rng.integers(0, self.nominal_time_period) # Option: Pick new offset
                     self.logger.debug(f"Node 0 (ours) got ADV success, new offset {self.offset}")
                # Other nodes might be marked 'done' externally by the simulation script

            elif self.action == ACTION.SCAN:
                # Only 'ours' protocol performs scans that update the channel map
                if self.protocol_type == 'ours':
                    self.logger.info(f"Node {self.id}: ASN {self.ASN}, Scan Success")
                    self.metrics["scan_success"] += 1
                    # Update channel map at the corresponding slot index
                    slot_index = self.ASN % self.nominal_time_period
                    self.channel_map[slot_index] += 1 # Increment count for this slot
                    # Optional: Implement decay/aging for the channel map here if needed

        # Note: Energy cost deduction moved to do_action for better timing


    def print_stats(self):
        """Prints node metrics, adapted for protocol."""
        print(f"--- Node {self.id} ({self.protocol_type}) Metrics ---")
        print(f"  Adv Sent: {self.metrics['adv_sent']}")
        print(f"  Adv Success: {self.metrics['adv_success']}")
        if self.protocol_type == 'ours':
            print(f"  Scan Sent: {self.metrics['scan_sent']}")
            print(f"  Scan Success: {self.metrics['scan_success']}")
        print(f"------------------------------------")

    def run_one_time_step(self):
        """Main logic executed each time step, branching based on protocol."""
        # --- Common Logic ---
        # Get current ASN from clock
        clock_tick = self.clock_subscriber.get_message()
        if clock_tick is not None and clock_tick > self.ASN:
             self.ASN = clock_tick
        elif clock_tick is None and self.ASN == 0:
             pass # Wait for first clock tick
        # else: # Handle potential missed ticks? For now, assume clock is reliable.
             # self.logger.warning(f"Node {self.id} missed clock tick? Current: {self.ASN}, Received: {clock_tick}")


        # Harvest energy (even if OFF)
        harvested_energy = self.energy_harvester.get_energy()
        # Apply energy update and check for state transitions (ON/OFF/Reset)
        self.compute_energy_level(harvested_energy)

        # Default action is SLEEP
        self.action = ACTION.SLEEP

        # --- Protocol-Specific Logic ---
        if self.state == STATE.ON:
            self.ran_once = True # Mark that the node has been ON at least once

            # --- 'ours' Protocol Logic ---
            if self.protocol_type == 'ours':
                # Apply runtype override if applicable
                if self.runtype == RUN_TYPE.ADVERTISING:
                    self.action = ACTION.ADVERTISE
                elif self.runtype == RUN_TYPE.SCANNING:
                    self.action = ACTION.SCAN # Note: Ensure do_action handles this if energy cost differs
                elif self.runtype == RUN_TYPE.NORMAL:
                    # Decide action for this ON cycle if not already decided
                    if not self.action_decided_this_cycle:
                        # MODIFIED: Use self.rng instead of random
                        if self.rng.random() < self.alpha:
                            # Chose to ADVERTISE this cycle
                            self.scans_remaining_this_cycle = 0
                            # Schedule advertisement: Check channel map first
                            if np.any(self.channel_map > 0):
                                target_slot = np.argmax(self.channel_map)
                            else:
                                target_slot = self.offset # Fallback to own offset

                            # Calculate ASN for the target slot in the current or next cycle
                            current_slot_in_cycle = self.ASN % self.nominal_time_period
                            if current_slot_in_cycle <= target_slot:
                                self.next_adv_wakeup = self.ASN + (target_slot - current_slot_in_cycle)
                            else:
                                self.next_adv_wakeup = self.ASN + (self.nominal_time_period - current_slot_in_cycle + target_slot)
                            self.logger.debug(f"Node {self.id} chose ADV, scheduled for ASN {self.next_adv_wakeup} (target slot {target_slot})")

                        else:
                            # Chose to SCAN this cycle
                            self.scans_remaining_this_cycle = self.n_scans_per_charge
                            self.next_adv_wakeup = -1 # Not advertising this cycle
                            self.logger.debug(f"Node {self.id} chose SCAN ({self.scans_remaining_this_cycle} scans)")

                        self.action_decided_this_cycle = True

                    # Execute scheduled actions
                    if self.next_adv_wakeup == self.ASN:
                        self.action = ACTION.ADVERTISE
                        self.next_adv_wakeup = -1 # Reset schedule after firing
                        self.action_decided_this_cycle = False # Ready for next decision when ON again
                    elif self.scans_remaining_this_cycle > 0:
                        # Probabilistically perform a scan
                        # Spread scans over the nominal period
                        scan_probability = self.n_scans_per_charge / self.nominal_time_period
                        # MODIFIED: Use self.rng instead of random
                        if self.rng.random() < scan_probability:
                             self.action = ACTION.SCAN
                             self.scans_remaining_this_cycle -= 1
                             if self.scans_remaining_this_cycle == 0:
                                 self.action_decided_this_cycle = False # Ready for next decision
                        # else: action remains SLEEP

            # --- 'baseline' Protocol Logic ---
            elif self.protocol_type == 'baseline':
                # Check if it's time for the scheduled advertisement
                if self.scheduled_advertisement_time != -1 and self.ASN == self.scheduled_advertisement_time:
                    self.action = ACTION.ADVERTISE
                    self.scheduled_advertisement_time = -1 # Reset schedule after firing
                # else: action remains SLEEP

        # --- Perform Action ---
        # If node is OFF, action remains SLEEP
        self.do_action(self.action)


    def reset(self):
        """Resets node state when voltage drops below VOFF."""
        self.logger.debug(f"Node {self.id} resetting at ASN {self.ASN}")
        self.state = STATE.OFF
        # self.energy_level = 0 # Option: Fully discharge on reset? Or keep residual? Keep residual for now.
        self.action = ACTION.SLEEP

        # Reset protocol-specific states
        if self.protocol_type == 'ours':
            self.channel_map = np.zeros(self.nominal_time_period)
            self.next_adv_wakeup = -1
            self.action_decided_this_cycle = False
            self.scans_remaining_this_cycle = 0
            # Keep the same offset? Or re-randomize? Re-randomize for now.
            # MODIFIED: Use self.rng instead of random
            self.offset = self.rng.integers(0, self.nominal_time_period)

        elif self.protocol_type == 'baseline':
            self.scheduled_advertisement_time = -1

        # Do not reset self.ran_once here, as it tracks if the node *ever* turned on
