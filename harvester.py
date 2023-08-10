## The harvester will be outputing the energy harvested per clock tick.
## It can also do that with a input file for the energy harvested per clock tick.

import numpy as np
import random
from enum import Enum
import math
import logging

from interface import Subscriber

class harvestingmode(Enum):
    CONSTANT = 0
    GAUSSIAN =1
    FILE = 2

class Harvester:
    def __init__(self, mode, file, clock, log_level=logging.INFO):
        self.mode = mode
        self.file = file
        self.energy_harvested = 0
        self.clock = clock
        self.subscriber = Subscriber("clock", self.clock)
        self.previous_tick = 0
        self.energy_per_clock_tick = 0
        self.mean = 0
        self.std = 0
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
    
    def set_constant(self, energy_per_clock_tick):
        self.energy_per_clock_tick = energy_per_clock_tick
    
    def set_gaussian(self, mean, std):
        self.mean = mean
        self.std = std
    

    def get_energy(self):
        new_tick = self.subscriber.get_message()
        if(new_tick == self.previous_tick + 1 or self.previous_tick == 0):
            self.previous_tick = new_tick
            if self.mode == harvestingmode.CONSTANT:
                return self.energy_per_clock_tick
            elif self.mode == harvestingmode.GAUSSIAN:
                return np.random.normal(self.mean, self.std)
            elif self.mode == harvestingmode.FILE:
                return self.file.readline()
            else:
                self.logger.error("No harvesting mode set")
                return 0
            
            
        else:
            self.logger.error("Clock ticks are not in order: " + str(new_tick) + " " + str(self.previous_tick))
            return 0