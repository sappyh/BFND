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
        self._v_brownout = None
        self._eadv = None
        self._v_max_thr = None
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

    def with_energy_parameters(self, capacitance, von, voff, v_brownout, eadv, v_max_thr):
        self._capacitance = capacitance
        self._von = von
        self._voff = voff
        self._v_brownout = v_brownout
        self._eadv = eadv
        self._v_max_thr = v_max_thr
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
        if self._capacitance is None or self._von is None or self._voff is None or self._v_brownout is None or self._eadv is None or self._v_max_thr is None:
            raise ValueError("Energy parameters (capacitance, von, voff, v_brownout, eadv, v_max_thr) are required")
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
            v_brownout=self._v_brownout,
            eadv=self._eadv,
            v_max_thr=self._v_max_thr,
            nominal_time_period=self._nominal_time_period,
            rng=self._rng,
            runtype=self._runtype,
            log_level=self._log_level
        )
