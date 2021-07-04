import logging
from json import loads
from typing import Tuple

import pika
import telegram


def parse_data(body: bytes, bot) -> Tuple[telegram.Message, telegram.User]:
    data = loads(body.decode())
    message = telegram.Message.de_json(data['message'], bot)
    user = telegram.User.de_json(data['user'], bot)
    return message, user


class Connector:
    def __init__(self, queue, host='localhost', port=None):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host))
        self.chanel = self.connection.channel()
        self.queue = queue
        self.chanel.queue_declare(queue=queue, durable=True)

    def publish(self, message: str):
        try:
            self.chanel.basic_publish(exchange='', routing_key=self.queue, body=message.encode())
            return True
        except Exception as e:
            logging.exception(e)
