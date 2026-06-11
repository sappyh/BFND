import math
import logging
from src.node.enums import ACTION, STATE, RADIO_STATE, RUN_TYPE
from src.messaging.Subscriber import Subscriber

class Node:
    def __init__(self, id, energy_harvester, clock, radio, protocol, capacitance, von, voff, eadv, nominal_time_period, rng, runtype=RUN_TYPE.NORMAL, log_level=logging.INFO):
        self.id = id
        self.energy_harvester = energy_harvester
        # Unique subscriber topic
        self.clock_subscriber = Subscriber(f"clock_node_{id}", clock)
        self.radio = radio
        self.protocol = protocol
        self.runtype = runtype
        self.rng = rng

        # --- Energy Parameters ---
        self.capacitance = capacitance
        self.von = von
        self.voff = voff
        self.eadv = eadv
        self.esleep = 10.5e-9
        self.ebusy_wait = 309e-9

        # --- Timing Parameters ---
        self.nominal_time_period = nominal_time_period
        self.ASN = 0

        # --- State Variables ---
        self.state = STATE.OFF
        self.energy_level = 0.0
        self.action = ACTION.SLEEP
        self.done = False
        self.ran_once = False

        # --- Logging ---
        self.logger = logging.getLogger(f"Node_{id}")
        self.logger.setLevel(log_level)
        self.logger.disabled = True

        # --- Metrics ---
        self.metrics = {
            "adv_sent": 0,
            "adv_success": 0
        }

        # Initialize protocol-specific attributes/metrics
        if self.protocol:
            self.protocol.initialize(self)

        self.logger.info(f"Initialized Node {self.id}")

    def compute_energy_level(self, energy_in):
        prev_voltage = math.sqrt(max(0.0, 2 * self.energy_level / self.capacitance))

        self.energy_level += energy_in
        if self.energy_level < 0:
            self.energy_level = 0.0

        voltage = math.sqrt(max(0.0, 2 * self.energy_level / self.capacitance))

        if prev_voltage < self.voff and voltage >= self.voff:
            if self.protocol:
                self.protocol.on_voltage_above_voff(self)

        if voltage < self.voff and self.ran_once:
            self.reset()

        if self.state == STATE.OFF and voltage >= self.von:
            self.state = STATE.ON
            self.logger.debug(f"Node {self.id} turned ON at ASN {self.ASN}")
            if self.protocol:
                self.protocol.on_turn_on(self)

        elif self.state == STATE.ON and voltage < self.voff:
            self.state = STATE.OFF
            self.logger.debug(f"Node {self.id} turned OFF at ASN {self.ASN} due to low voltage")
            if self.protocol:
                self.protocol.on_turn_off(self)

    def do_action(self, action_to_do):
        if self.state == STATE.ON:
            cost = 0.0
            if action_to_do == ACTION.ADVERTISE:
                self.radio.advertise(self.ASN, self.id)
                self.metrics["adv_sent"] += 1
                cost = self.eadv
                self.logger.debug(f"Node {self.id} performing ADV at ASN {self.ASN}")
            elif action_to_do == ACTION.SCAN:
                # Get escan cost from protocol (defaults to 0 if not present)
                escan = getattr(self.protocol, 'escan', 0.0)
                self.radio.scan(self.ASN, self.id)
                if self.protocol and hasattr(self.protocol, 'metrics'):
                    self.protocol.metrics["scan_sent"] = self.protocol.metrics.get("scan_sent", 0) + 1
                cost = escan
                self.logger.debug(f"Node {self.id} performing SCAN at ASN {self.ASN}")

            if action_to_do == ACTION.SLEEP:
                self.radio.sleep()
                if self.ran_once:
                    cost = self.esleep
            elif action_to_do == ACTION.BUSY_WAIT:
                self.radio.sleep()
                if self.ran_once:
                    cost = self.ebusy_wait

            if cost > 0:
                self.compute_energy_level(-cost)
        else:
            self.radio.sleep()

    def build_channel_map(self):
        radio_outcome = self.radio.get_message()
        if self.protocol:
            self.protocol.process_radio_outcome(self, radio_outcome)

    def print_stats(self):
        print(f"--- Node {self.id} Metrics ---")
        print(f"  Adv Sent: {self.metrics['adv_sent']}")
        print(f"  Adv Success: {self.metrics['adv_success']}")
        if self.protocol:
            self.protocol.print_stats(self)
        print(f"------------------------------------")

    def run_one_time_step(self):
        clock_tick = self.clock_subscriber.get_message()
        if clock_tick is not None and clock_tick > self.ASN:
            self.ASN = clock_tick
        elif clock_tick is None and self.ASN == 0:
            pass

        harvested_energy = self.energy_harvester.get_energy()
        self.compute_energy_level(harvested_energy)

        self.action = ACTION.SLEEP

        if self.state == STATE.ON:
            self.ran_once = True
            if self.runtype == RUN_TYPE.ADVERTISING:
                self.action = ACTION.ADVERTISE
            elif self.runtype == RUN_TYPE.SCANNING:
                self.action = ACTION.SCAN
            elif self.runtype == RUN_TYPE.NORMAL:
                if self.protocol:
                    self.action = self.protocol.decide_action(self)

        self.do_action(self.action)

    def reset(self):
        self.logger.debug(f"Node {self.id} resetting at ASN {self.ASN}")
        self.state = STATE.OFF
        self.action = ACTION.SLEEP
        if self.protocol:
            self.protocol.reset(self)
