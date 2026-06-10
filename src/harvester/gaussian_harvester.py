import logging
import random
from src.harvester.IHarvester import HarvesterInterface
from src.messaging.Subscriber import Subscriber

class GaussianHarvester(HarvesterInterface):
    def __init__(self, clock_publisher, mean=0.0, std=0.0, log_level=logging.INFO, nominal_runtime=1000):
        self.mean = mean
        self.std = std
        self.clock_publisher = clock_publisher
        subscriber_topic = f"harvester_clock_sub_{id(self)}"
        self.clock_subscriber = Subscriber(subscriber_topic, self.clock_publisher)
        self.logger = logging.getLogger(f"GaussianHarvester_{id(self)}")
        self.logger.setLevel(log_level)

    def set_gaussian(self, mean, std):
        self.mean = mean
        self.std = std

    def get_energy(self):
        new_tick = self.clock_subscriber.get_message()
        if new_tick is None:
            return 0.0
        return max(0.0, random.gauss(self.mean, self.std))

    def close(self):
        if self.clock_subscriber:
            try:
                self.clock_subscriber.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting subscriber: {e}")
