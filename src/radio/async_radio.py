from enum import Enum
import logging
from src.radio.IRadio import RadioInterface
from src.messaging.Subscriber import Subscriber
from src.node.enums import RADIO_STATE

class RadioEvent(Enum):
    ADVERTISE = 1
    SCAN = 2

def check_tx_overlap(t1, t2):
    def overlap(s1, e1, s2, e2):
        return max(s1, s2) < min(e1, e2)
    
    return (overlap(t1, t1 + 0.048, t2, t2 + 0.048) or
            overlap(t1, t1 + 0.048, t2 + 0.928, t2 + 0.976) or
            overlap(t1 + 0.928, t1 + 0.976, t2, t2 + 0.048) or
            overlap(t1 + 0.928, t1 + 0.976, t2 + 0.928, t2 + 0.976))

class AsyncRadioMessage:
    def __init__(self, ASN, radioEvent, nodeID, phase_shift=0.0, loglevel=logging.INFO):
        self.ASN = ASN
        self.radioEvent = radioEvent
        self.nodeID = nodeID
        self.phase_shift = phase_shift
        self.logger = logging.getLogger(f"RadioMessage_Node{nodeID}")
        self.logger.setLevel(loglevel)
        self.logger.disabled = True

    def check_message(self, message):
        if message is None:
            return RADIO_STATE.FAILURE
        
        t1 = self.ASN + self.phase_shift
        t2 = message.ASN + message.phase_shift
        
        if self.radioEvent == RadioEvent.ADVERTISE:
            if message.radioEvent == RadioEvent.ADVERTISE:
                abs_diff = abs(t1 - t2)
                # Node discovery succeeds if the absolute difference in physical times is between 88us (0.088ms) and 840us (0.840ms)
                if 0.088 <= abs_diff <= 0.840:
                    self.logger.debug(f"ADV Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN} (t1={t1:.3f}, t2={t2:.3f})")
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
            else:
                return RADIO_STATE.FAILURE
        elif self.radioEvent == RadioEvent.SCAN:
            if message.radioEvent == RadioEvent.ADVERTISE:
                # Scanner active in [t1, t1 + 1.0]. Advertiser TX1 in [t2, t2 + 0.048], TX2 in [t2 + 0.928, t2 + 0.976]
                tx1_in = (t1 <= t2) and (t2 + 0.048 <= t1 + 1.0)
                tx2_in = (t1 <= t2 + 0.928) and (t2 + 0.976 <= t1 + 1.0)
                if tx1_in or tx2_in:
                    self.logger.debug(f"SCAN Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN} (t1={t1:.3f}, t2={t2:.3f})")
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
            else:
                return RADIO_STATE.FAILURE
        return RADIO_STATE.FAILURE

class AsyncRadio(RadioInterface):
    def __init__(self, publisher=None, loglevel=logging.INFO):
        self.publisher = publisher
        self.transmit_message = None
        self.transmitted_message = None
        self.subscribers = []
        self.subscribe_done = False
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.history_received_messages = []
        self.logger = logging.getLogger(f"Radio_{id(self)}")
        self.logger.setLevel(loglevel)
        self.logger.disabled = True

    def connectto(self, other_radio):
        # I listen to other_radio
        if other_radio.publisher:
            sub1 = Subscriber("NBDiscovery", other_radio.publisher)
            self.subscribers.append(sub1)
            self.logger.debug(f"Radio {id(self)} connected subscriber to NBDiscovery")
        
        # other_radio listens to me
        if self.publisher:
            sub2 = Subscriber("NBDiscovery", self.publisher)
            other_radio.subscribers.append(sub2)
            other_radio.logger.debug(f"Radio {id(other_radio)} connected subscriber to NBDiscovery")

    def advertise(self, asn, nodeID, phase_shift):
        self.logger.debug(f"Node {nodeID} preparing ADV for ASN {asn}")
        message = AsyncRadioMessage(asn, RadioEvent.ADVERTISE, nodeID, phase_shift=phase_shift, loglevel=self.logger.getEffectiveLevel())
        self.transmit_message = message
        self.transmitted_message = None
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.subscribe_done = False

    def scan(self, asn, nodeID, phase_shift):
        self.logger.debug(f"Node {nodeID} preparing SCAN for ASN {asn}")
        message = AsyncRadioMessage(asn, RadioEvent.SCAN, nodeID, phase_shift=phase_shift, loglevel=self.logger.getEffectiveLevel())
        self.transmitted_message = message
        self.transmit_message = None
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.subscribe_done = False

    def get_message(self):
        if self.subscribe_done:
            self.subscribe_done = False
            outcome = self.receive_message_outcome
            interacted_id = getattr(self, 'last_interacted_node_id', None)
            self.transmitted_message = None
            self.receive_message_outcome = RADIO_STATE.FAILURE
            self.last_interacted_node_id = None
            return outcome, interacted_id
        else:
            self.logger.warning(f"Radio {id(self)}: get_message called before subscribe step completed.")
            return RADIO_STATE.FAILURE, None

    def sleep(self):
        self.transmit_message = None
        self.transmitted_message = None
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.last_interacted_node_id = None

    def publish(self):
        if self.transmit_message is not None:
            msg_to_send = self.transmit_message
            self.transmitted_message = msg_to_send
            self.transmit_message = None
            if self.publisher:
                self.publisher.publish(msg_to_send)
            return msg_to_send
        return None

    def subscribe(self):
        if not self.subscribers:
            self.logger.error(f"Radio {id(self)}: Subscribe called but not connected to any publisher.")
            self.subscribe_done = True
            return

        new_messages = []
        for sub in self.subscribers:
            n_msgs = sub.get_number_of_messages()
            for _ in range(n_msgs):
                msg = sub.get_message()
                if msg:
                    new_messages.append(msg)
                    
        # Add new messages to history
        self.history_received_messages.extend(new_messages)

        # Determine current ASN for history purging
        if self.transmitted_message is not None:
            current_asn = self.transmitted_message.ASN
        elif new_messages:
            current_asn = max(msg.ASN for msg in new_messages)
        elif self.history_received_messages:
            current_asn = max(msg.ASN for msg in self.history_received_messages)
        else:
            current_asn = None

        if current_asn is not None:
            # Purge messages older than current_asn - 2
            self.history_received_messages = [
                msg for msg in self.history_received_messages
                if msg.ASN >= current_asn - 2
            ]

        n_messages = len(self.history_received_messages)

        current_outcome = RADIO_STATE.FAILURE

        if self.transmitted_message is not None:
            if n_messages == 0:
                current_outcome = RADIO_STATE.FAILURE
            elif n_messages == 1:
                current_outcome = self.transmitted_message.check_message(self.history_received_messages[0])
                if current_outcome == RADIO_STATE.SUCCESS:
                    if self.transmitted_message.radioEvent == RadioEvent.ADVERTISE:
                        self.logger.debug(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction with Node {self.history_received_messages[0].nodeID} at ASN {self.transmitted_message.ASN}")
                        self.last_interacted_node_id = self.history_received_messages[0].nodeID
                    else:
                        self.logger.debug(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction (Energy Detected) at ASN {self.transmitted_message.ASN}")
                        self.last_interacted_node_id = None
            else:
                ## Multiple messages is allowed with Scan 
                if self.transmitted_message.radioEvent == RadioEvent.ADVERTISE:
                    successful_msgs = []
                    for i, msg in enumerate(self.history_received_messages):
                        if self.transmitted_message.check_message(msg) == RADIO_STATE.SUCCESS:
                            collides = False
                            for j, other_msg in enumerate(self.history_received_messages):
                                if i != j:
                                    t1 = msg.ASN + msg.phase_shift
                                    t2 = other_msg.ASN + other_msg.phase_shift
                                    if check_tx_overlap(t1, t2):
                                        collides = True
                                        break
                            if not collides:
                                successful_msgs.append(msg)
                    
                    if successful_msgs:
                        current_outcome = RADIO_STATE.SUCCESS
                        self.last_interacted_node_id = successful_msgs[0].nodeID
                        self.logger.debug(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction with Node {self.last_interacted_node_id} at ASN {self.transmitted_message.ASN} despite multiple messages")
                    else:
                        self.logger.info(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Interference detected ({n_messages} messages) at ASN {self.transmitted_message.ASN}")
                        current_outcome = RADIO_STATE.FAILURE
                else:
                    self.logger.info(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction (Energy Detected) at ASN {self.transmitted_message.ASN}")
                    current_outcome = RADIO_STATE.SUCCESS
                    self.last_interacted_node_id = None

        self.receive_message_outcome = current_outcome
        self.subscribe_done = True
