import threading
import queue

class Publisher:
    def __init__(self, topic):
        self.topic = topic
        self.subscribers = []
    
    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)
    
    def publish(self, message):
        for subscriber in self.subscribers:
            subscriber.notify(message)


class Subscriber:
    def __init__(self, topic, publisher):
        self.topic = topic
        self.message_queue = queue.Queue()
        self.subscribe(publisher)
    
    def subscribe(self, publisher):
        publisher.subscribe(self)
    
    def notify(self, message):
        if message is not None:
            self.message_queue.put(message)

    def get_message(self):
        message = None
        if(self.message_queue.qsize() > 0):
            message = self.message_queue.get()

        return message
    
    def get_number_of_messages(self):
        n = self.message_queue.qsize()
        return n