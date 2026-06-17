import logging

class RadioInterface:
    def connectto(self, other_radio):
        raise NotImplementedError

    def advertise(self, asn, node_id, phase_shift):
        raise NotImplementedError

    def scan(self, asn, node_id, phase_shift):
        raise NotImplementedError

    def get_message(self):
        raise NotImplementedError

    def sleep(self):
        raise NotImplementedError

    def publish(self):
        raise NotImplementedError

    def subscribe(self):
        raise NotImplementedError

class RadioFactory:
    @staticmethod
    def create_radio(radio_type="simple", publisher=None, log_level=logging.INFO):
        if radio_type == "async":
            from .async_radio import AsyncRadio
            return AsyncRadio(publisher, log_level)
        else:
            from .simple_radio import SimpleRadio
            return SimpleRadio(publisher, log_level)
