## clock for the node

from interface import Publisher
from time import sleep


class Clock:
    def __init__(self,ticks_per_seconds, publisher):
        self.ticks_per_seconds = ticks_per_seconds
        self.publisher = publisher
        self.ticks = 0
        
    
    ##  a method to broadcast a clock tick
    def tick(self):
        self.ticks += 1
        self.publisher.publish(self.ticks)

    def get_ticks_per_seconds(self):
        return self.ticks_per_seconds