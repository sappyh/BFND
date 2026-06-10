from src.protocol.IProtocol import ProtocolInterface
from src.node.enums import ACTION, STATE, RADIO_STATE

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

def get_optimal_scale(t_chr):
    if t_chr >= scale_table[0][0]:
        return scale_table[0][1]
    if t_chr <= scale_table[-1][0]:
        return scale_table[-1][1]
        
    for i in range(len(scale_table) - 1):
        if scale_table[i+1][0] <= t_chr <= scale_table[i][0]:
            x0, y0 = scale_table[i]
            x1, y1 = scale_table[i+1]
            return y0 + (t_chr - x0) * (y1 - y0) / (x1 - x0)
            
    return 0.0284599 # Default fallback

class Find(ProtocolInterface):
    def __init__(self):
        self.scheduled_advertisement_time = -1
        self.last_turn_off_time = 0
        self.metrics = {}

    def initialize(self, node):
        pass

    def on_turn_on(self, node):
        current_t_chr = node.ASN if self.last_turn_off_time == 0 else (node.ASN - self.last_turn_off_time)
        p = get_optimal_scale(current_t_chr)
        
        # Sample from geometric distribution (failures before first success, i.e. >= 0)
        # In numpy, geometric(p) returns values >= 1. Subtracting 1 gives values >= 0.
        delay = node.rng.geometric(p) - 1
        
        self.scheduled_advertisement_time = node.ASN + delay
        node.logger.debug(f"Node {node.id} (Find) scheduled ADV for ASN {self.scheduled_advertisement_time} (delay={delay}, p={p})")

    def on_turn_off(self, node):
        self.scheduled_advertisement_time = -1

    def on_voltage_above_voff(self, node):
        self.last_turn_off_time = node.ASN

    def decide_action(self, node) -> ACTION:
        if self.scheduled_advertisement_time != -1 and node.ASN == self.scheduled_advertisement_time:
            self.scheduled_advertisement_time = -1
            return ACTION.ADVERTISE
        return ACTION.SLEEP

    def process_radio_outcome(self, node, radio_outcome):
        if radio_outcome == RADIO_STATE.SUCCESS and node.state == STATE.ON:
            if node.action == ACTION.ADVERTISE:
                node.logger.info(f"Node {node.id}: ASN {node.ASN}, Advertise Success")
                node.metrics["adv_success"] += 1

    def reset(self, node):
        self.scheduled_advertisement_time = -1
        ## self.last_turn_off_time = 0 ## Disable reset of last turn off time for Find

    def print_stats(self, node):
        pass

    def get_metrics(self) -> dict:
        return self.metrics
