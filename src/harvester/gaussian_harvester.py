import logging
import random
from src.harvester.IHarvester import HarvesterInterface
from src.messaging.Subscriber import Subscriber

class GaussianHarvester(HarvesterInterface):
    def __init__(self, clock_publisher, mean=0.0, std=0.0, log_level=logging.INFO):
        self.mean = mean
        self.std = std
        self.clock_publisher = clock_publisher
        subscriber_topic = f"harvester_clock_sub_{id(self)}"
        self.clock_subscriber = Subscriber(subscriber_topic, self.clock_publisher)
        self.logger = logging.getLogger(f"GaussianHarvester_{id(self)}")
        self.logger.setLevel(log_level)
        self.cached_energy = 0.0

    def set_gaussian(self, mean, std):
        self.mean = mean
        self.std = std

    def get_energy(self):
        new_tick = self.clock_subscriber.get_message() if self.clock_subscriber else None
        if new_tick is None:
            return self.cached_energy
        self.cached_energy = max(0.0, random.gauss(self.mean, self.std))
        return self.cached_energy

    def get_energy_fast(self, slot):
        self.cached_energy = max(0.0, random.gauss(self.mean, self.std))
        return self.cached_energy

    def close(self):
        if self.clock_subscriber:
            try:
                self.clock_subscriber.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting subscriber: {e}")
            self.clock_subscriber = None
