import numpy as np
from enum import Enum

from src.node.enums import ACTION, RADIO_STATE
from src.protocol.IProtocol import ProtocolInterface


class BFNDState(Enum):
    UNINITIALIZED = 0
    ADVERTISEMENT = 1
    SCAN = 2


class BFND(ProtocolInterface):
    def __init__(self, alpha, eadv, escan, offset, nominal_time_period, node_id, rng, logger, use_adv_delay=False):
        self.alpha = float(alpha)
        self.eadv = float(eadv)
        self.escan = float(escan)
        self.offset = offset
        self.nominal_time_period = nominal_time_period
        self.node_id = node_id
        self.rng = rng
        self.logger = logger
        self.use_adv_delay = use_adv_delay

        self.channel_map = np.zeros(nominal_time_period)
        self.n_scans_per_charge = 1
        self.scans_remaining_this_cycle = 0
        self.state = BFNDState.UNINITIALIZED
        self.next_adv_wakeup = -1

        self.metrics = {
            "scan_sent": 0,
            "scan_success": 0,
        }

    def initialize(self):
        if self.escan > 0:
            self.n_scans_per_charge = max(1, int(self.eadv / self.escan))
        else:
            self.n_scans_per_charge = 1
        self.state = BFNDState.UNINITIALIZED
        self.next_adv_wakeup = -1
        self.scans_remaining_this_cycle = 0

    def _enter_advertisement_state(self, asn: int):
        current_slot_in_cycle = asn % self.nominal_time_period

        candidate_slots = [self.offset]
        if np.any(self.channel_map > 0):
            non_zero_slots = np.where(self.channel_map > 0)[0]
            candidate_slots.extend(non_zero_slots)

        candidate_slots = np.array(candidate_slots)
        delays = (candidate_slots - current_slot_in_cycle) % self.nominal_time_period
        
        # argmin returns the first occurrence of the minimum, so if multiple slots tie, 
        # it will pick the first one (self.offset is at index 0)
        target_slot = int(candidate_slots[np.argmin(delays)])
        delay = int(np.min(delays))

        if delay == 0:
            delay = self.nominal_time_period

        # BLE-style advDelay: add a random delay of 0 to 10 slots (ms) to prevent consecutive collisions
        adv_delay = int(self.rng.integers(0, 11)) if self.use_adv_delay else 0
        self.next_adv_wakeup = asn + delay + adv_delay
        self.state = BFNDState.ADVERTISEMENT
        self.logger.debug(
            f"Node {self.node_id} chose ADV, scheduled for ASN {self.next_adv_wakeup} (target slot {target_slot}, delay={delay}, advDelay={adv_delay})"
        )

    def _enter_scan_state(self):
        self.scans_remaining_this_cycle = self.n_scans_per_charge
        self.state = BFNDState.SCAN
        self.logger.debug(f"Node {self.node_id} chose SCAN ({self.scans_remaining_this_cycle} scans)")

    def _reset_charge_state(self):
        self.next_adv_wakeup = -1
        self.scans_remaining_this_cycle = 0
        self.state = BFNDState.UNINITIALIZED

    def on_turn_on(self, asn: int):
        self._reset_charge_state()

    def on_turn_off(self, asn: int):
        self._reset_charge_state()

    def on_voltage_above_vmax_thr(self, asn: int):
        pass

    def on_voltage_below_von(self, asn: int):
        pass

    def decide_action(self, asn: int, available_energy: float) -> ACTION:
        if self.state == BFNDState.UNINITIALIZED:
            if self.rng.random() < self.alpha:
                self._enter_advertisement_state(asn)
            else:
                self._enter_scan_state()
            return ACTION.SLEEP

        if self.state == BFNDState.ADVERTISEMENT:
            if self.next_adv_wakeup == asn:
                self.next_adv_wakeup = -1
                self.state = BFNDState.UNINITIALIZED
                return ACTION.ADVERTISE

        if self.state == BFNDState.SCAN:
            if self.scans_remaining_this_cycle <= 0:
                self._reset_charge_state()
                return ACTION.SLEEP

            # Scans are very cheap, so consume them back-to-back (one per slot)
            # instead of spreading them probabilistically across the cycle.
            self.scans_remaining_this_cycle -= 1
            self.metrics["scan_sent"] += 1
            if self.scans_remaining_this_cycle == 0:
                self.state = BFNDState.UNINITIALIZED
            return ACTION.SCAN

        return ACTION.SLEEP

    def evaluate_time_step(self, asn: int, radio_outcome, action_taken):
        if radio_outcome == RADIO_STATE.SUCCESS:
            if action_taken == ACTION.ADVERTISE:
                if self.node_id == 0:
                    self.offset = int(self.rng.integers(0, self.nominal_time_period))
                    self.logger.debug(f"Node 0 (bfnd) got ADV success, new offset {self.offset}")
            elif action_taken == ACTION.SCAN:
                self.metrics["scan_success"] += 1
                slot_index = asn % self.nominal_time_period
                self.channel_map[slot_index] += 1

    def reset(self, asn: int):
        self._reset_charge_state()
        self.offset = int(self.rng.integers(0, self.nominal_time_period))

    def print_stats(self):
        print(f"  Scan Sent: {self.metrics['scan_sent']}")
        print(f"  Scan Success: {self.metrics['scan_success']}")

    def get_metrics(self) -> dict:
        return self.metrics
