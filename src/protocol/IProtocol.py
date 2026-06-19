import logging

import numpy as np


class ProtocolInterface:
    def initialize(self):
        raise NotImplementedError

    def on_turn_on(self, asn: int):
        raise NotImplementedError

    def on_turn_off(self, asn: int):
        raise NotImplementedError

    def decide_action(self, asn: int, available_energy: float) -> int:
        raise NotImplementedError

    def evaluate_time_step(self, asn: int, radio_outcome, action_taken):
        raise NotImplementedError

    def reset(self, asn: int):
        raise NotImplementedError

    def on_voltage_above_voff(self, asn: int):
        pass

    def on_voltage_above_vmax_thr(self, asn: int):
        pass

    def on_voltage_below_von(self, asn: int):
        pass

    def print_stats(self):
        raise NotImplementedError

    def get_metrics(self) -> dict:
        raise NotImplementedError


class ProtocolFactory:
    @staticmethod
    def create_protocol(protocol_type, **kwargs):
        from .bfnd import BFND
        from .find import Find

        protocol_type_lower = protocol_type.lower()
        if protocol_type_lower in ('ours', 'bfnd', 'bfnd-ble', 'bfnd_ble'):
            alpha = kwargs.get('alpha')
            eadv = kwargs.get('eadv')
            escan = kwargs.get('escan')
            offset = kwargs.get('offset')
            nominal_time_period = kwargs.get('nominal_time_period')
            node_id = kwargs.get('node_id')
            rng = kwargs.get('rng')
            logger = kwargs.get('logger')
            use_adv_delay = protocol_type_lower in ('bfnd-ble', 'bfnd_ble')
            return BFND(alpha, eadv, escan, offset, nominal_time_period, node_id, rng, logger, use_adv_delay=use_adv_delay)
        elif protocol_type_lower in ('baseline', 'find'):
            node_id = kwargs.get('node_id')
            rng = kwargs.get('rng')
            logger = kwargs.get('logger')
            nominal_time_period = kwargs.get('nominal_time_period')
            return Find(node_id, rng, logger, nominal_time_period)
        else:
            raise ValueError(f"Unknown protocol type: {protocol_type}")
