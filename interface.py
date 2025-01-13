import threading
import queue
import logging


class Publisher:
    def __init__(self, topic):
        self.topic = topic
        self.subscribers = []

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def publish(self, message):
        for subscriber in self.subscribers:
            try:
                subscriber.notify(message)
            except Exception as e:
                logging.error(f"Publisher {self.topic}: Failed to notify subscriber {subscriber.topic}: {e}.")


class Subscriber:
    def __init__(self, topic, publisher):
        self.topic = topic
        self.message_queue = queue.Queue()
        self.subscribe(publisher)

    def subscribe(self, publisher):
        publisher.subscribe(self)

    def notify(self, message):
        try:
            self.message_queue.put(message, block=False)  # Non-blocking put
        except queue.Full:
            discarded = self.message_queue.get()  # Remove the oldest message
            self.message_queue.put(message)  # Add the new message
            logging.warning(
                f"Subscriber {self.topic}: Queue full. Dropped oldest message {discarded}. Queue size: {self.message_queue.qsize()}.")

    def get_message(self):
        message = None
        if (self.message_queue.qsize() > 0):
            try:
                message = self.message_queue.get(timeout=1)  # Timeout after 1 second
            except queue.Empty:
                logging.warning(f"Subscriber {self}: No messages to process.")

        return message

    def get_number_of_messages(self):
        n = self.message_queue.qsize()
        return n

    def shutdown(self):
        #logging.debug(f"Subscriber {self.topic}: Shutting down. Clearing queue.")
        while not self.message_queue.empty():
            discarded = self.message_queue.get()
            #logging.debug(f"Subscriber {self.topic}: Discarded message during shutdown: {discarded}.")
