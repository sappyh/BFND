import numpy as np
from src.protocol.IProtocol import ProtocolInterface
from src.node.enums import ACTION, STATE, RADIO_STATE

class BFND(ProtocolInterface):
    def __init__(self, alpha, escan, offset, nominal_time_period):
        self.alpha = alpha
        self.escan = escan
        self.offset = offset
        self.nominal_time_period = nominal_time_period
        
        self.channel_map = np.zeros(nominal_time_period)
        self.n_scans_per_charge = 1
        self.scans_remaining_this_cycle = 0
        self.action_decided_this_cycle = False
        self.next_adv_wakeup = -1
        self.is_scanning_from_vmax = False
        
        self.metrics = {
            "scan_sent": 0,
            "scan_success": 0
        }

    def initialize(self, node):
        if self.escan > 0:
            self.n_scans_per_charge = max(1, int(node.eadv / self.escan))
        else:
            self.n_scans_per_charge = 1

    def on_turn_on(self, node):
        self.action_decided_this_cycle = False
        self.scans_remaining_this_cycle = 0
        self.next_adv_wakeup = -1
        self.is_scanning_from_vmax = False

    def on_turn_off(self, node):
        self.next_adv_wakeup = -1
        self.action_decided_this_cycle = False
        self.is_scanning_from_vmax = False

    def on_voltage_above_vmax_thr(self, node):
        self.is_scanning_from_vmax = True
        node.logger.debug(f"Node {node.id} reached V_MAX_THR, constantly scanning...")

    def on_voltage_below_von(self, node):
        if self.is_scanning_from_vmax:
            self.is_scanning_from_vmax = False
            node.logger.debug(f"Node {node.id} dropped below von, stopped constantly scanning.")

    def decide_action(self, node) -> ACTION:
        if self.is_scanning_from_vmax:
            return ACTION.SCAN

        if not self.action_decided_this_cycle:
            if node.rng.random() < self.alpha:
                self.scans_remaining_this_cycle = 0
                if np.any(self.channel_map > 0):
                    target_slot = np.argmax(self.channel_map)
                else:
                    target_slot = self.offset

                current_slot_in_cycle = node.ASN % self.nominal_time_period
                if current_slot_in_cycle <= target_slot:
                    self.next_adv_wakeup = node.ASN + (target_slot - current_slot_in_cycle)
                else:
                    self.next_adv_wakeup = node.ASN + (self.nominal_time_period - current_slot_in_cycle + target_slot)
                node.logger.debug(f"Node {node.id} chose ADV, scheduled for ASN {self.next_adv_wakeup} (target slot {target_slot})")
            else:
                self.scans_remaining_this_cycle = self.n_scans_per_charge
                self.next_adv_wakeup = -1
                node.logger.debug(f"Node {node.id} chose SCAN ({self.scans_remaining_this_cycle} scans)")

            self.action_decided_this_cycle = True

        if self.next_adv_wakeup == node.ASN:
            self.next_adv_wakeup = -1
            self.action_decided_this_cycle = False
            return ACTION.ADVERTISE
        elif self.scans_remaining_this_cycle > 0:
            scan_probability = self.n_scans_per_charge / self.nominal_time_period
            if node.rng.random() < scan_probability:
                self.scans_remaining_this_cycle -= 1
                if self.scans_remaining_this_cycle == 0:
                    self.action_decided_this_cycle = False
                return ACTION.SCAN
        
        return ACTION.SLEEP

    def process_radio_outcome(self, node, radio_outcome):
        if radio_outcome == RADIO_STATE.SUCCESS and node.state == STATE.ON:
            if node.action == ACTION.ADVERTISE:
                node.logger.info(f"Node {node.id}: ASN {node.ASN}, Advertise Success")
                node.metrics["adv_success"] += 1
                if node.id == 0:
                    self.offset = node.rng.integers(0, self.nominal_time_period)
                    node.logger.debug(f"Node 0 (bfnd) got ADV success, new offset {self.offset}")
            elif node.action == ACTION.SCAN:
                node.logger.info(f"Node {node.id}: ASN {node.ASN}, Scan Success")
                self.metrics["scan_success"] += 1
                slot_index = node.ASN % self.nominal_time_period
                self.channel_map[slot_index] += 1

    def reset(self, node):
        self.channel_map = np.zeros(self.nominal_time_period)
        self.next_adv_wakeup = -1
        self.action_decided_this_cycle = False
        self.scans_remaining_this_cycle = 0
        self.offset = node.rng.integers(0, self.nominal_time_period)
        self.is_scanning_from_vmax = False

    def print_stats(self, node):
        print(f"  Scan Sent: {self.metrics['scan_sent']}")
        print(f"  Scan Success: {self.metrics['scan_success']}")

    def get_metrics(self) -> dict:
        return self.metrics
