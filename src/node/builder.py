import logging
from src.node.enums import RUN_TYPE
from src.node.node import Node

class NodeBuilder:
    def __init__(self):
        self._id = None
        self._energy_harvester = None
        self._clock = None
        self._radio = None
        self._protocol = None
        self._capacitance = None
        self._von = None
        self._voff = None
        self._eadv = None
        self._nominal_time_period = None
        self._rng = None
        self._runtype = RUN_TYPE.NORMAL
        self._log_level = logging.INFO

    def with_id(self, id):
        self._id = id
        return self

    def with_energy_harvester(self, harvester):
        self._energy_harvester = harvester
        return self

    def with_clock(self, clock):
        self._clock = clock
        return self

    def with_radio(self, radio):
        self._radio = radio
        return self

    def with_protocol(self, protocol):
        self._protocol = protocol
        return self

    def with_energy_parameters(self, capacitance, von, voff, eadv):
        self._capacitance = capacitance
        self._von = von
        self._voff = voff
        self._eadv = eadv
        return self

    def with_nominal_time_period(self, nominal_time_period):
        self._nominal_time_period = nominal_time_period
        return self

    def with_rng(self, rng):
        self._rng = rng
        return self

    def with_runtype(self, runtype):
        self._runtype = runtype
        return self

    def with_log_level(self, log_level):
        self._log_level = log_level
        return self

    def build(self) -> Node:
        if self._id is None:
            raise ValueError("Node id is required")
        if self._energy_harvester is None:
            raise ValueError("Energy harvester is required")
        if self._clock is None:
            raise ValueError("Clock/Clock Publisher is required")
        if self._radio is None:
            raise ValueError("Radio is required")
        if self._capacitance is None or self._von is None or self._voff is None or self._eadv is None:
            raise ValueError("Energy parameters (capacitance, von, voff, eadv) are required")
        if self._nominal_time_period is None:
            raise ValueError("Nominal time period is required")
        if self._rng is None:
            raise ValueError("RNG is required")

        return Node(
            id=self._id,
            energy_harvester=self._energy_harvester,
            clock=self._clock,
            radio=self._radio,
            protocol=self._protocol,
            capacitance=self._capacitance,
            von=self._von,
            voff=self._voff,
            eadv=self._eadv,
            nominal_time_period=self._nominal_time_period,
            rng=self._rng,
            runtype=self._runtype,
            log_level=self._log_level
        )
