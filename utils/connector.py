import logging
import os
import sys
import time
from typing import Union

import pika

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


class Connector:
    def __init__(self, queue, host='localhost', port=None, max_count_tries=5):

        self.connection = self.get_connection(host)
        self.channel = self.connection.channel()
        self.queue = queue
        self.channel.queue_declare(queue=queue, durable=True)
        self.max_count_tries = max_count_tries

    def get_connection(self, host):
        self.max_count_tries = 5
        cur_try = 1
        logging.info(f'Trying to connect to AMQP on host: {host}')
        while True:
            try:
                logging.info(f'Try #{cur_try}')
                return pika.BlockingConnection(pika.ConnectionParameters(host))
            except pika.connection.exceptions.AMQPError as exc:
                if self.max_count_tries == cur_try:
                    raise exc
                cur_try += 1
                time.sleep(2)

    def publish(self, message: Union[str, bytes]):
        try:
            if isinstance(message, str):
                self.channel.basic_publish(exchange='', routing_key=self.queue, body=message.encode())
            elif isinstance(message, bytes):
                self.channel.basic_publish(exchange='', routing_key=self.queue, body=message)
            return True
        except Exception as e:
            logging.exception(e)


class Listener:
    def __init__(self, queue):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = connection.channel()
        self.channel.queue_declare(queue=queue, durable=True)  # , durable=True
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue, on_message_callback=self._callback, consumer_tag='telegram_connector')

    def callback(self, body: bytes):
        raise NotImplemented

    def _callback(self, ch, method, properties, body: bytes):
        self.callback(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        try:
            self.channel.start_consuming()
        except Exception as exc:
            print(exc)
        except KeyboardInterrupt:
            print('Interrupted')
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)

    async def run(self):
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            loop.run_in_executor(None, self.start())
        except KeyboardInterrupt:
            print('Interrupted')
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)
