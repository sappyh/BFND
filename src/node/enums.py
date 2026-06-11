from enum import Enum

class ACTION(Enum):
    SLEEP = 0
    ADVERTISE = 1
    SCAN = 2
    BUSY_WAIT = 3

class STATE(Enum):
    ON = 1
    OFF = 0

class RADIO_STATE(Enum):
    SUCCESS = 1
    FAILURE = 0

class RUN_TYPE(Enum):
    SCANNING = 0
    ADVERTISING = 1
    NORMAL = 2
