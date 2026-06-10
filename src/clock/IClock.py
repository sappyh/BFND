class ClockInterface:
    def tick(self):
        raise NotImplementedError

    def get_ticks_per_seconds(self) -> int:
        raise NotImplementedError

class ClockFactory:
    @staticmethod
    def create_clock(ticks_per_seconds, publisher):
        from .clock import Clock
        return Clock(ticks_per_seconds, publisher)
