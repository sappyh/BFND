import threading
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
        self.message = []
        self.lock = threading.Lock()
        self.subscribe(publisher)
    
    def subscribe(self, publisher):
        publisher.subscribe(self)
    
    def notify(self, message):
        self.lock.acquire()
        if message is None:
            self.lock.release()
        else:
            self.message.append(message)
            self.lock.release()

    def get_message(self):
        self.lock.acquire()
        if(len(self.message) > 0):
            message = self.message.pop(0)
            self.lock.release()
            return message
        else:
            self.lock.release()
            return None
    
    def get_number_of_messages(self):
        self.lock.acquire()
        n = len(self.message)
        self.lock.release()
        return n