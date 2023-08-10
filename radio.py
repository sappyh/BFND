## This is a software which takes in messages from the nodes and publishes them to the other radios
## Have to expose the radio publsihing interface to the nodes
## Have to expose the radio subscribing interface to the radios
from interface import Publisher, Subscriber
from node import RADIO_STATE
from enum import Enum
import threading
import time

import logging


class RadioEvent(Enum):
    ADVERTISE = 1
    SCAN = 2

class radioMessage:
    def __init__(self, ASN, radioEvent, nodeID, loglevel = logging.INFO):
        self.ASN  = ASN
        self.radioEvent = radioEvent
        self.nodeID = nodeID
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(loglevel)

    def check_message(self, message):
        if message is None:
            return RADIO_STATE.FAILURE
        if(self.ASN == message.ASN):
            if(self.radioEvent == RadioEvent.ADVERTISE):
                if(message.radioEvent == RadioEvent.ADVERTISE):
                    self.logger.debug("Message :node id: %s ASN: %s radioEvent: %s", str(message.nodeID), str(message.ASN), " " + str(message.radioEvent))
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
            elif(self.radioEvent == RadioEvent.SCAN):
                if(message.radioEvent == RadioEvent.ADVERTISE):
                    self.logger.debug("Message : node id: %s ASN: %s radioEvent: %s", str(message.nodeID), str(message.ASN), " " + str(message.radioEvent))
                    return RADIO_STATE.SUCCESS
                else:
                    return RADIO_STATE.FAILURE
                
class Radio:
    def __init__(self, loglevel = logging.INFO):
        self.publisher = Publisher("radio")
        self.transmit_message = None
        self.transmitted_message = None
        self.lock = threading.Lock()
        self.subscribe_done = False
        self.receive_message = False
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(loglevel)
    
    # Functions used by the node
    def connectto(self, other_radio):
        self.subscriber = Subscriber("radio", getattr(other_radio, "publisher"))
   
    def advertise(self, asn, nodeID):
        self.logger.debug("Advertising")
        message = radioMessage(asn, RadioEvent.ADVERTISE, nodeID)
        self.transmit_message = message
        self.receive_message = False
        self.lock.acquire()
        self.subscribe_done = False
        self.lock.release()

    def scan(self, asn, nodeID):
        self.logger.debug("Scanning")
        message = radioMessage(asn, RadioEvent.SCAN, nodeID)
        self.transmit_message = message
        self.receive_message = False
        self.lock.acquire()
        self.subscribe_done = False
        self.lock.release()
    
    def get_message(self):
        while True:
            self.lock.acquire()
            if(self.subscribe_done == True):
                self.lock.release()
                break
            self.lock.release()
            time.sleep(0.1)

        return RADIO_STATE.SUCCESS if self.receive_message == RADIO_STATE.SUCCESS else RADIO_STATE.FAILURE

    # Functions used by the simulation
    def publish(self):
        if self.transmit_message is not None:
            self.logger.debug("Publishing : node id: %s ASN: %s radioEvent: %s", str(self.transmit_message.nodeID), str(self.transmit_message.ASN), " " + str(self.transmit_message.radioEvent))
            self.publisher.publish(self.transmit_message)
            self.transmitted_message = self.transmit_message
            self.transmit_message = None
    
    def subscribe(self):
        n = self.subscriber.get_number_of_messages()
        if n>1 and self.transmitted_message is not None:
            self.log.info("Interference: More than one message in the queue")
            for i in range(n):
                message= self.subscriber.get_message()
                self.logger.debug("Received : node id: %s ASN: %s radioEvent: %s", str(message.nodeID), str(message.ASN), " " + str(message.radioEvent))
        elif self.transmitted_message is not None:
                self.receive_message = self.transmitted_message.check_message(self.subscriber.get_message())
        else:
            # Removing the messages from the queue
            for i in range(n):
                message= self.subscriber.get_message()

        self.transmitted_message = None
        self.lock.acquire()
        self.subscribe_done = True
        self.lock.release()
        

    def sleep(self):
        self.transmit_message = None
        