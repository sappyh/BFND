# --- Imports ---
from interface import Publisher, Subscriber
from node import RADIO_STATE
from enum import Enum
import logging

# --- Enums and Classes ---
class RadioEvent(Enum):
    """ Represents the type of radio event. """
    ADVERTISE = 1
    SCAN = 2

class radioMessage:
    """ Represents a message transmitted over the radio. """
    def __init__(self, ASN, radioEvent, nodeID, loglevel=logging.INFO):
        self.ASN = ASN
        self.radioEvent = radioEvent
        self.nodeID = nodeID
        # Each message instance gets its own logger if needed, or inherit from Radio
        self.logger = logging.getLogger(f"RadioMessage_Node{nodeID}")
        self.logger.setLevel(loglevel)
        # Disable per-message logging by default if too verbose
        self.logger.disabled = True

    def check_message(self, message):
        """
        Checks if an incoming message constitutes a successful reception
        based on the current radio's intended action (self).
        Returns RADIO_STATE.SUCCESS or RADIO_STATE.FAILURE.
        """
        if message is None:
            return RADIO_STATE.FAILURE
        # Check if the message occurred at the same time slot (ASN)
        if self.ASN == message.ASN:
            # Case 1: This radio was advertising
            if self.radioEvent == RadioEvent.ADVERTISE:
                # Success if the other radio was also advertising (bidirectional discovery)
                # or if the other radio was scanning (unidirectional discovery - ADV heard by SCAN)
                # Current implementation checks only for ADV <-> ADV
                if message.radioEvent == RadioEvent.ADVERTISE:
                    self.logger.debug(f"ADV Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN}")
                    return RADIO_STATE.SUCCESS
                else:
                    # Failure if advertising and received a scan or nothing relevant
                    return RADIO_STATE.FAILURE
            # Case 2: This radio was scanning
            elif self.radioEvent == RadioEvent.SCAN:
                # Success if the other radio was advertising
                if message.radioEvent == RadioEvent.ADVERTISE:
                    self.logger.debug(f"SCAN Success: Self Node {self.nodeID} heard ADV from Node {message.nodeID} at ASN {self.ASN}")
                    return RADIO_STATE.SUCCESS
                else:
                    # Failure if scanning and received a scan or nothing relevant
                    return RADIO_STATE.FAILURE
        # Messages are not from the same time slot
        return RADIO_STATE.FAILURE

class Radio:
    """ Simulates a radio transceiver for a node. """
    def __init__(self, loglevel=logging.INFO):
        # Note: The publisher is now external, managed by the simulation script
        # self.publisher = Publisher("radio") # Removed internal publisher
        self.transmit_message = None # Message to be sent in the next publish step
        self.transmitted_message = None # Copy of the message that was actually sent
        self.subscriber = None # Subscriber instance, created in connectto
        self.subscribe_done = False # Flag indicating subscription processing is complete for the step
        self.receive_message_outcome = RADIO_STATE.FAILURE # Stores the outcome of the last reception attempt
        self.logger = logging.getLogger(f"Radio_{id(self)}") # Unique logger per radio instance
        self.logger.setLevel(loglevel)
        self.logger.disabled = True # Disable radio logging by default if needed

    # --- Methods used by the Node ---

    def connectto(self, other_radio, publisher_to_subscribe_to):
        """
        Connects this radio's subscriber to the specified publisher.
        Args:
            other_radio: The other Radio object (used potentially for context, not directly subscribed to).
            publisher_to_subscribe_to: The Publisher instance for the communication channel.
        """
        if self.subscriber is None:
            # Create a subscriber linked to the specific publisher channel
            # Generate a unique topic name for the subscriber for clarity in logs
            # Node ID isn't directly available here, use radio's unique ID
            subscriber_topic = f"radio_sub_{id(self)}_listens_{publisher_to_subscribe_to.topic}"
            self.subscriber = Subscriber(subscriber_topic, publisher_to_subscribe_to)
            self.logger.debug(f"Radio {id(self)} connected subscriber to {publisher_to_subscribe_to.topic}")
        else:
            # Handle case where connectto might be called multiple times if necessary
            # For now, assume it's called once per required connection setup
            self.logger.warning(f"Radio {id(self)}: connectto called but subscriber already exists. Ignoring.")
            # If re-subscription or multi-channel subscription is needed, logic goes here.

    def advertise(self, asn, nodeID):
        """ Prepares an advertisement message for transmission. """
        self.logger.debug(f"Node {nodeID} preparing ADV for ASN {asn}")
        message = radioMessage(asn, RadioEvent.ADVERTISE, nodeID, loglevel=self.logger.getEffectiveLevel())
        self.transmit_message = message
        self.transmitted_message = None # Clear previous transmitted message state
        self.receive_message_outcome = RADIO_STATE.FAILURE # Reset outcome for the new cycle
        self.subscribe_done = False

    def scan(self, asn, nodeID):
        """ Prepares the radio state for scanning (listening). """
        self.logger.debug(f"Node {nodeID} preparing SCAN for ASN {asn}")
        # Create a message representing the scan action for checking incoming messages
        message = radioMessage(asn, RadioEvent.SCAN, nodeID, loglevel=self.logger.getEffectiveLevel())
        self.transmitted_message = message # Store the scan action context
        self.transmit_message = None # Radio is listening, not transmitting
        self.receive_message_outcome = RADIO_STATE.FAILURE # Reset outcome
        self.subscribe_done = False

    def get_message(self):
        """
        Called by the Node to get the outcome of its last radio action (ADV or SCAN).
        Returns RADIO_STATE.SUCCESS or RADIO_STATE.FAILURE.
        """
        # Return the stored outcome only if the subscription step is done for this tick
        if self.subscribe_done:
            # Reset the flag so the outcome isn't retrieved multiple times per tick
            self.subscribe_done = False
            # Return the determined outcome
            outcome = self.receive_message_outcome
            # Reset internal state after node retrieves the message
            self.transmitted_message = None # Clear the context of the last action
            self.receive_message_outcome = RADIO_STATE.FAILURE # Reset for next cycle
            return outcome
        else:
            # If subscribe step hasn't finished, outcome is not ready
            # This shouldn't happen with the current simulation loop structure
            self.logger.warning(f"Radio {id(self)}: get_message called before subscribe step completed.")
            return RADIO_STATE.FAILURE

    def sleep(self):
        """ Sets the radio to a non-transmitting, non-scanning state. """
        self.transmit_message = None
        self.transmitted_message = None # Clear last action context
        self.receive_message_outcome = RADIO_STATE.FAILURE # Reset outcome
        # Should subscribe_done be reset here? Depends on loop structure.
        # If sleep happens before subscribe, maybe. If after, maybe not.
        # For safety, let's assume subscribe might still run.


    # --- Methods used by the Simulation Loop ---

    def publish(self):
        """ Transmits the prepared message using the external publisher. """
        # This radio instance doesn't own the publisher directly anymore.
        # The simulation loop needs to get the message and publish it on the correct channel.
        # This method might need refactoring or removal depending on simulation loop design.

        # --- Revised Approach: Return message to simulation loop ---
        if self.transmit_message is not None:
             msg_to_send = self.transmit_message
             # Store the message that was intended for transmission
             self.transmitted_message = msg_to_send
             # Clear the message to be sent for the next step
             self.transmit_message = None
             # Return the message for the simulation loop to publish
             return msg_to_send
        return None # Nothing to transmit


    def subscribe(self):
        """ Processes messages received from the subscribed publisher for this tick. """
        if self.subscriber is None:
            self.logger.error(f"Radio {id(self)}: Subscribe called but not connected to any publisher.")
            self.subscribe_done = True # Mark as done even if error
            return

        n_messages = self.subscriber.get_number_of_messages()
        received_messages = []
        for _ in range(n_messages):
            msg = self.subscriber.get_message()
            if msg:
                received_messages.append(msg)

        # Default outcome is failure
        current_outcome = RADIO_STATE.FAILURE

        # Check outcome only if this radio performed an action (ADV or SCAN)
        if self.transmitted_message is not None:
            if n_messages == 0:
                # No messages received, action failed
                current_outcome = RADIO_STATE.FAILURE
            elif n_messages == 1:
                # One message received, check if it's a successful interaction
                current_outcome = self.transmitted_message.check_message(received_messages[0])
                if current_outcome == RADIO_STATE.SUCCESS:
                     self.logger.debug(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Successful interaction with Node {received_messages[0].nodeID} at ASN {self.transmitted_message.ASN}")
            else: # n_messages > 1
                # Collision / Interference
                self.logger.info(f"Radio {id(self)} (Node {self.transmitted_message.nodeID}): Interference detected ({n_messages} messages) at ASN {self.transmitted_message.ASN}")
                # Check if any message would have resulted in success (e.g., scan hearing multiple ads)
                # Simple model: Assume collision results in failure for both ADV and SCAN
                current_outcome = RADIO_STATE.FAILURE
                # More complex models could allow SCAN to succeed if at least one ADV is heard clearly.

        # Store the final outcome for this tick
        self.receive_message_outcome = current_outcome
        # Mark subscription processing as done for this tick
        self.subscribe_done = True
