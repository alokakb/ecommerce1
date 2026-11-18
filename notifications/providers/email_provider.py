from abc import ABC, abstractmethod

class EmailProvider(ABC):
    @abstractmethod
    def send_mail(self, *, recipient, subject, body):
        pass