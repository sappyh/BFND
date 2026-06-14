import math
import logging
from src.node.enums import ACTION, STATE, RADIO_STATE, RUN_TYPE
from src.messaging.Subscriber import Subscriber

class Node:
    def __init__(self, id, energy_harvester, clock, radio, protocol, capacitance, von, voff, v_brownout, eadv, v_max_thr, nominal_time_period, rng, runtype=RUN_TYPE.NORMAL, log_level=logging.INFO):
        self.id = id
        self.energy_harvester = energy_harvester
        # Unique subscriber topic
        self.clock_subscriber = Subscriber(f"clock_node_{id}", clock)
        self.radio = radio
        self.protocol = protocol
        self.runtype = runtype
        self.rng = rng

        # --- Energy Parameters ---
        self.capacitance = float(capacitance)
        self.von = float(von)
        self.voff = float(voff)
        self.v_brownout = float(v_brownout)
        self.eadv = float(eadv)
        self.v_max_thr = float(v_max_thr)
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
        self.logger.disabled = False    

        # --- Metrics ---
        self.metrics = {
            "adv_sent": 0,
            "adv_success": 0,
            "discovered_nodes": set()
        }

        # Initialize protocol-specific attributes/metrics
        if self.protocol:
            self.protocol.initialize()

        self.logger.info(f"Initialized Node {self.id}")

    def _available_energy_above_voff(self):
        voff_energy = 0.5 * self.capacitance * self.voff * self.voff
        return max(0.0, self.energy_level - voff_energy)

    def compute_energy_level(self, energy_in):
        prev_voltage = math.sqrt(max(0.0, 2 * self.energy_level / self.capacitance))

        self.energy_level += energy_in
        if self.energy_level < 0:
            self.energy_level = 0.0

        voltage = math.sqrt(max(0.0, 2 * self.energy_level / self.capacitance))

        if prev_voltage < self.voff and voltage >= self.voff:
            if self.protocol:
                self.protocol.on_voltage_above_voff(self.ASN)

        if prev_voltage < self.v_max_thr and voltage >= self.v_max_thr:
            if self.protocol and hasattr(self.protocol, 'on_voltage_above_vmax_thr'):
                self.protocol.on_voltage_above_vmax_thr(self.ASN)

        if prev_voltage > self.von and voltage <= self.von:
            if self.protocol and hasattr(self.protocol, 'on_voltage_below_von'):
                self.protocol.on_voltage_below_von(self.ASN)

        if voltage < self.v_brownout and self.ran_once:
            self.reset()

        if self.state == STATE.OFF and voltage >= self.von:
            self.state = STATE.ON
            self.logger.debug(f"Node {self.id} turned ON at ASN {self.ASN}")
            if self.protocol:
                self.protocol.on_turn_on(self.ASN)

        elif self.state == STATE.ON and voltage < self.voff:
            self.state = STATE.OFF
            self.logger.debug(f"Node {self.id} turned OFF at ASN {self.ASN} due to low voltage")
            if self.protocol:
                self.protocol.on_turn_off(self.ASN)

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

    def evaluate_time_step(self):
        radio_outcome, interacted_id = self.radio.get_message()
        if radio_outcome == RADIO_STATE.SUCCESS and self.state == STATE.ON and self.action == ACTION.ADVERTISE:
            if interacted_id is not None:
                self.metrics["discovered_nodes"].add(interacted_id)
                self.metrics["adv_success"] = len(self.metrics["discovered_nodes"])
                logging.getLogger(f"Node_{self.id}").debug(f"Node {self.id} got ADV success at ASN {self.ASN}")
        if self.protocol:
            self.protocol.evaluate_time_step(self.ASN, radio_outcome, self.action)

    def print_stats(self):
        print(f"--- Node {self.id} Metrics ---")
        print(f"  Adv Sent: {self.metrics['adv_sent']}")
        print(f"  Adv Success: {self.metrics['adv_success']}")
        if self.protocol:
            self.protocol.print_stats()
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
                    self.action = self.protocol.decide_action(self.ASN, self._available_energy_above_voff())

        self.do_action(self.action)

    def reset(self):
        self.logger.debug(f"Node {self.id} resetting at ASN {self.ASN}")
        self.state = STATE.OFF
        self.action = ACTION.SLEEP
        if self.protocol:
            self.protocol.reset(self.ASN)
