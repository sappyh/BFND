import logging
from src.harvester.IHarvester import HarvesterInterface
from src.messaging.Subscriber import Subscriber

class ConstantHarvester(HarvesterInterface):
    def __init__(self, clock_publisher, power=0.0, log_level=logging.INFO):
        self.power = power
        self.clock_publisher = clock_publisher
        subscriber_topic = f"harvester_clock_sub_{id(self)}"
        self.clock_subscriber = Subscriber(subscriber_topic, self.clock_publisher)
        self.logger = logging.getLogger(f"ConstantHarvester_{id(self)}")
        self.logger.setLevel(log_level)
        self.cached_energy = 0.0

    def set_constant(self, power):
        self.power = power

    def get_energy(self):
        new_tick = self.clock_subscriber.get_message() if self.clock_subscriber else None
        if new_tick is None:
            return self.cached_energy
        self.cached_energy = self.power
        return self.power

    def get_energy_fast(self, slot):
        self.cached_energy = self.power
        return self.power

    def close(self):
        if self.clock_subscriber:
            try:
                self.clock_subscriber.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting subscriber: {e}")
            self.clock_subscriber = None
