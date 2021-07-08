import logging
import time

import pika


class Connector:
    def __init__(self, queue, host='localhost', port=None):

        self.connection = self.get_connection(host)
        self.channel = self.connection.channel()
        self.queue = queue
        self.channel.queue_declare(queue=queue, durable=True)

    @staticmethod
    def get_connection(host):
        tries = 10
        cur_try = 0
        logging.info('Trying to connect to AMQP')
        while True:
            try:
                logging.info(f'Try #{cur_try}')
                return pika.BlockingConnection(pika.ConnectionParameters(host))
            except pika.connection.exceptions.AMQPError as exc:
                if tries == cur_try:
                    raise exc
                cur_try += 1
                time.sleep(2)

    def publish(self, message: str):
        try:
            self.channel.basic_publish(exchange='', routing_key=self.queue, body=message.encode())
            return True
        except Exception as e:
            logging.exception(e)
