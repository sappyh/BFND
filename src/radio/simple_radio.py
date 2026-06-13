from enum import Enum
import logging
from src.radio.IRadio import RadioInterface
from src.messaging.Subscriber import Subscriber
from src.node.enums import RADIO_STATE

class RadioEvent(Enum):
    ADVERTISE = 1
    SCAN = 2

class RadioMessage:
    def __init__(self, ASN, radioEvent, nodeID, loglevel=logging.INFO):
        self.ASN = ASN
        self.radioEvent = radioEvent
        self.nodeID = nodeID
        self.logger = logging.getLogger(f"RadioMessage_Node{nodeID}")
        self.logger.setLevel(loglevel)
        self.logger.disabled = True

    def check_message(self, message):
        if message is None:
            return RADIO_STATE.FAILURE
        if self.ASN == message.ASN:
            if self.radioEvent == RadioEvent.ADVERTISE:
                if message.radioEvent == RadioEvent.ADVERTISE:
                    self.logger.debug(f"ADV Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN}")
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
            elif self.radioEvent == RadioEvent.SCAN:
                if message.radioEvent == RadioEvent.ADVERTISE:
                    self.logger.debug(f"SCAN Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN}")
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
        return RADIO_STATE.FAILURE

# Alias for backward compatibility
radioMessage = RadioMessage

class SimpleRadio(RadioInterface):
    def __init__(self, loglevel=logging.INFO):
        self.transmit_message = None
        self.transmitted_message = None
        self.subscribers = []
        self.subscribe_done = False
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.logger = logging.getLogger(f"Radio_{id(self)}")
        self.logger.setLevel(loglevel)
        self.logger.disabled = True

    def connectto(self, other_radio, publisher_to_subscribe_to):
        subscriber_topic = f"radio_sub_{id(self)}_listens_{publisher_to_subscribe_to.topic}"
        sub = Subscriber(subscriber_topic, publisher_to_subscribe_to)
        self.subscribers.append(sub)
        self.logger.debug(f"Radio {id(self)} connected subscriber to {publisher_to_subscribe_to.topic}")

    def advertise(self, asn, nodeID):
        self.logger.debug(f"Node {nodeID} preparing ADV for ASN {asn}")
        message = RadioMessage(asn, RadioEvent.ADVERTISE, nodeID, loglevel=self.logger.getEffectiveLevel())
        self.transmit_message = message
        self.transmitted_message = None
        self.receive_message_outcome = RADIO_STATE.FAILURE
        self.subscribe_done = False

    def scan(self, asn, nodeID):
        self.logger.debug(f"Node {nodeID} preparing SCAN for ASN {asn}")
        message = RadioMessage(asn, RadioEvent.SCAN, nodeID, loglevel=self.logger.getEffectiveLevel())
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
            return msg_to_send
        return None

    def subscribe(self):
        if not self.subscribers:
            self.logger.error(f"Radio {id(self)}: Subscribe called but not connected to any publisher.")
            self.subscribe_done = True
            return

        received_messages = []
        for sub in self.subscribers:
            n_msgs = sub.get_number_of_messages()
            for _ in range(n_msgs):
                msg = sub.get_message()
                if msg:
                    received_messages.append(msg)
                    
        n_messages = len(received_messages)

        current_outcome = RADIO_STATE.FAILURE

        if self.transmitted_message is not None:
            if n_messages == 0:
                current_outcome = RADIO_STATE.FAILURE
            elif n_messages == 1:
                current_outcome = self.transmitted_message.check_message(received_messages[0])
                if current_outcome == RADIO_STATE.SUCCESS:
                    self.logger.debug(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction with Node {received_messages[0].nodeID} at ASN {self.transmitted_message.ASN}")
                    self.last_interacted_node_id = received_messages[0].nodeID
            else:
                self.logger.info(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Interference detected ({n_messages} messages) at ASN {self.transmitted_message.ASN}")
                current_outcome = RADIO_STATE.FAILURE

        self.receive_message_outcome = current_outcome
        self.subscribe_done = True
