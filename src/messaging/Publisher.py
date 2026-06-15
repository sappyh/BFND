import logging

class Publisher:
    def __init__(self, topic):
        self.topic = topic
        self.subscribers = []

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        if subscriber in self.subscribers:
            self.subscribers.remove(subscriber)

    def publish(self, message):
        for subscriber in self.subscribers:
            try:
                subscriber.notify(message)
            except Exception as e:
                logging.error(f"Publisher {self.topic}: Failed to notify subscriber {subscriber.topic}: {e}.")
