import logging

class RadioInterface:
    def connectto(self, other_radio, publisher_to_subscribe_to):
        raise NotImplementedError

    def advertise(self, asn, node_id):
        raise NotImplementedError

    def scan(self, asn, node_id):
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
    def create_radio(log_level=logging.INFO):
        from .simple_radio import SimpleRadio
        return SimpleRadio(log_level)
