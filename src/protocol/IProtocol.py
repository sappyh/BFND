class ProtocolInterface:
    def initialize(self, node):
        raise NotImplementedError
    def on_turn_on(self, node):
        raise NotImplementedError
    def on_turn_off(self, node):
        raise NotImplementedError
    def decide_action(self, node) -> int:
        raise NotImplementedError
    def process_radio_outcome(self, node, radio_outcome):
        raise NotImplementedError
    def reset(self, node):
        raise NotImplementedError
    def on_voltage_above_voff(self, node):
        pass
    def on_voltage_above_vmax_thr(self, node):
        pass
    def on_voltage_below_von(self, node):
        pass
    def print_stats(self, node):
        raise NotImplementedError
    def get_metrics(self) -> dict:
        raise NotImplementedError

class ProtocolFactory:
    @staticmethod
    def create_protocol(protocol_type, **kwargs):
        from .bfnd import BFND
        from .find import Find

        protocol_type_lower = protocol_type.lower()
        if protocol_type_lower in ('ours', 'bfnd'):
            alpha = kwargs.get('alpha')
            escan = kwargs.get('escan')
            offset = kwargs.get('offset')
            nominal_time_period = kwargs.get('nominal_time_period')
            return BFND(alpha, escan, offset, nominal_time_period)
        elif protocol_type_lower in ('baseline', 'find'):
            return Find()
        else:
            raise ValueError(f"Unknown protocol type: {protocol_type}")

