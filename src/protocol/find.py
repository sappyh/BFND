from src.node.enums import ACTION, RADIO_STATE
from src.protocol.IProtocol import ProtocolInterface
from enum import Enum
import math

# Look up table from paper as implemented in BFND_CPP
scale_table = [
    (2600, 0.01564), (2550, 0.01562), (2500, 0.01559), (2450, 0.015571754589061853),
    (2400, 0.015745610068201587), (2350, 0.01599138402841411), (2300, 0.016256677223224634),
    (2250, 0.016585003552802177), (2200, 0.016849906753140083), (2150, 0.017163965864924344),
    (2100, 0.017434873801408287), (2050, 0.01768650804004632), (2000, 0.01798381535786539),
    (1950, 0.018244488800845123), (1900, 0.01857072397360221), (1850, 0.01891458278358025),
    (1800, 0.01931253841200982), (1750, 0.019709687193494484), (1700, 0.02012229438873964),
    (1650, 0.020496883430770038), (1600, 0.020858655436891835), (1550, 0.021300583166675307),
    (1500, 0.021780239294083504), (1450, 0.022309625765504756), (1400, 0.022844136633320956),
    (1350, 0.023424076196607527), (1300, 0.023948800207266887), (1250, 0.02456378701108067),
    (1200, 0.025251999170021768), (1150, 0.025970837779526485), (1100, 0.02666198590933177),
    (1050, 0.027595236415894675), (1000, 0.028459962665340375), (950, 0.029468143901217055),
    (900, 0.030553514344472246), (850, 0.0317312468059753), (800, 0.032786667021635636),
    (750, 0.03444320716954128), (700, 0.03604479674419088), (650, 0.03772878125759367),
    (600, 0.03988124014783679), (550, 0.04225148574362008), (500, 0.04495736770935152),
    (450, 0.048169548020250384), (400, 0.05200206557978777), (350, 0.05678263992803234),
    (300, 0.06275390110637416), (250, 0.07064853503714108), (200, 0.08162253468723255),
    (150, 0.09523721651237368), (100, 0.12756012326620422), (95, 0.13162741909742123),
    (90, 0.1360414666363674), (85, 0.1417278033654288), (80, 0.147068374954429),
    (75, 0.15295236767946493), (70, 0.1594758097419207), (65, 0.1666626448457833),
    (60, 0.17668204800909043), (55, 0.18621076584626142), (50, 0.1971694394831866),
    (45, 0.20993846405836497), (40, 0.2250532633294418), (35, 0.2487218064633894),
    (30, 0.27290992267137204), (25, 0.30433114845446796), (20, 0.3473958282184392),
    (15, 0.41162111340203345), (10, 0.5243514859675414), (5, 0.8358041858099494)
]


scale_tab = [0.0] * 257
for i in range(257):
    t_chr = (i + 1) * 10
    for j in range(len(scale_table) - 1):
        if scale_table[j + 1][0] <= t_chr <= scale_table[j][0]:
            x0, y0 = scale_table[j]
            x1, y1 = scale_table[j + 1]
            scale_tab[i] = y0 + (t_chr - x0) * (y1 - y0) / (x1 - x0)
            break

def lookup_scale(t_chr: int) -> float:
    if t_chr < 10:
        return scale_tab[0]
    elif t_chr > 2560:
        return scale_tab[255]

    idx_low = (t_chr // 10) - 1
    val_low = scale_tab[idx_low]
    val_high = scale_tab[t_chr // 10]
    frac = (t_chr % 10) / 10.0
    return val_low + frac * (val_high - val_low)

def geometric_itf_sample(p: float, rng) -> int:
    y = rng.integers(0, 4096) / 4096.0
    p_clamped = min(0.999999, p)
    res_float = math.log(1.0 - y) / math.log(1.0 - p_clamped) - 1.0
    res = int(res_float)
    if res < 0:
        res = 0
    return res



class FindState(Enum):
    UNINITIALIZED = 0
    ADVERTISEMENT = 1

class Find(ProtocolInterface):
    def __init__(self, node_id, rng, logger, nominal_time_period):
        self.node_id = node_id
        self.rng = rng
        self.logger = logger
        self.nominal_time_period = nominal_time_period
        self.scheduled_advertisement_time = -1
        self.last_turn_off_time = 0
        self.metrics = {}
        self.state = FindState.UNINITIALIZED

    def initialize(self):
        pass

    def on_turn_on(self, asn: int):
        current_t_chr = asn if self.last_turn_off_time == 0 else (asn - self.last_turn_off_time)
        delay = geometric_itf_sample(lookup_scale(current_t_chr), self.rng)
        self.scheduled_advertisement_time = asn + delay
        self.logger.debug(
            f"Node {self.node_id} (Find) scheduled ADV for ASN {self.scheduled_advertisement_time} (delay={delay})"
        )
        self.state = FindState.ADVERTISEMENT

    def on_turn_off(self, asn: int):
        self.last_turn_off_time = asn
        self.state = FindState.UNINITIALIZED

    def on_voltage_above_voff(self, asn: int):
        self.state = FindState.UNINITIALIZED

    def on_voltage_above_vmax_thr(self, asn: int):
        self.scheduled_advertisement_time = asn
        self.state = FindState.ADVERTISEMENT
        self.logger.debug(
            f"Node {self.node_id} (Find) reached V_MAX_THR, scheduled immediate ADV for ASN {self.scheduled_advertisement_time}"
        )

    def decide_action(self, asn: int, available_energy: float) -> ACTION:
        if self.state == FindState.ADVERTISEMENT and asn == self.scheduled_advertisement_time:
            self.state = FindState.UNINITIALIZED
            return ACTION.ADVERTISE
        if self.state == FindState.ADVERTISEMENT:
            return ACTION.SLEEP
        if self.state == FindState.UNINITIALIZED:
            return ACTION.BUSY_WAIT
        

    def evaluate_time_step(self, asn: int, radio_outcome, action_taken):
        pass

    def reset(self, asn: int):
        self.scheduled_advertisement_time = -1
        self.state = FindState.UNINITIALIZED

    def print_stats(self):
        pass

    def get_metrics(self) -> dict:
        return self.metrics
