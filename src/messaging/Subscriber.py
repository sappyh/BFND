import collections
import logging

class Subscriber:
    def __init__(self, topic, publisher):
        self.topic = topic
        self.message_queue = collections.deque(maxlen=1000)
        self.subscribe(publisher)

    def subscribe(self, publisher):
        self.publisher = publisher
        publisher.subscribe(self)

    def unsubscribe(self):
        if hasattr(self, 'publisher') and self.publisher:
            self.publisher.unsubscribe(self)

    def notify(self, message):
        if len(self.message_queue) >= 1000:
            discarded = self.message_queue[0]
            logging.warning(
                f"Subscriber {self.topic}: Queue full. Dropped oldest message {discarded}. Queue size: {len(self.message_queue)}."
            )
        self.message_queue.append(message)

    def get_message(self):
        if self.message_queue:
            return self.message_queue.popleft()
        return None

    def get_number_of_messages(self):
        return len(self.message_queue)

    def shutdown(self):
        self.message_queue.clear()
