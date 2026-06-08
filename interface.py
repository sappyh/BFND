import collections
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
        self.message_queue = collections.deque(maxlen=1000)
        self.subscribe(publisher)

    def subscribe(self, publisher):
        publisher.subscribe(self)

    def notify(self, message):
        # If queue is full (reached maxlen), the oldest message is automatically discarded by deque.
        # We can check and log a warning if needed, but direct append is fastest.
        if len(self.message_queue) >= 1000:
            discarded = self.message_queue[0]
            logging.warning(
                f"Subscriber {self.topic}: Queue full. Dropped oldest message {discarded}. Queue size: {len(self.message_queue)}.")
        self.message_queue.append(message)

    def get_message(self):
        if self.message_queue:
            return self.message_queue.popleft()
        return None

    def get_number_of_messages(self):
        return len(self.message_queue)

    def shutdown(self):
        self.message_queue.clear()
