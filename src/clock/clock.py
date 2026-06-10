from src.clock.IClock import ClockInterface

class Clock(ClockInterface):
    def __init__(self, ticks_per_seconds, publisher):
        self.ticks_per_seconds = ticks_per_seconds
        self.publisher = publisher
        self.ticks = 0

    def tick(self):
        self.ticks += 1
        self.publisher.publish(self.ticks)

    def get_ticks_per_seconds(self):
        return self.ticks_per_seconds
