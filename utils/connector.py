import logging
import os
import sys
import time
from json import dumps, loads
from typing import Union, List

import pika

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


class Connector:
    def __init__(self, queue, host='localhost', port=5672, max_count_tries=5, *, lazy=False):
        self.queue = queue
        self.max_count_tries = max_count_tries

        self.channel = None
        self.connection = None
        if not lazy:
            self.connect(host, port)

    def get_connection(self, host, port):
        cur_try = 1
        logging.info(f'Trying to connect to AMQP on host: {host} port: {port}')
        while True:
            try:
                logging.info(f'Try #{cur_try}')
                return pika.BlockingConnection(pika.ConnectionParameters(host, port))
            except pika.connection.exceptions.AMQPError as exc:
                if self.max_count_tries == cur_try:
                    raise exc
                cur_try += 1
                time.sleep(2)

    def connect(self, host, port):
        self.connection = self.get_connection(host, port)
        self.prepare_channel()

    @property
    def has_connection(self) -> bool:
        return bool(self.channel) and bool(self.connection) and (self.connection.is_open or False)

    def prepare_channel(self):
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue, durable=True)

    def publish(self, message: Union[str, bytes]):

        try:
            if isinstance(message, str):
                self.channel.basic_publish(exchange='', routing_key=self.queue, body=message.encode())
            elif isinstance(message, bytes):
                self.channel.basic_publish(exchange='', routing_key=self.queue, body=message)
            return True
        except Exception as e:
            logging.exception(e)


class LazyConnector(Connector):
    def __init__(self, queue, host='localhost', port=5672):
        self.host = host
        self.port = port
        super(LazyConnector, self).__init__(queue, lazy=True)

    def publish(self, message: Union[str, bytes]):
        if not self.has_connection:
            self.connect(self.host, self.port)
        super(LazyConnector, self).publish(message)


class Listener:
    def __init__(self, queue, host='localhost', port=5672, consumer_tag='listener'):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))
        self.channel = connection.channel()
        self.channel.queue_declare(queue=queue, durable=True)  # , durable=True
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue, on_message_callback=self._callback, consumer_tag=consumer_tag)
        self._consumer_tag = consumer_tag

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

    def stop(self):
        self.channel.stop_consuming(self._consumer_tag)


class Notify(Connector):
    def __init__(self, host='localhost', port=5672, **kwargs):
        super(Notify, self).__init__('notify', host=host, port=port, **kwargs)

    def handle_insert(self, message, users: List[int]):
        # {'message': Message, 'users': List[users_id}
        self.publish(dumps({'message': message.to_dict(), 'users': users}, default=str))


class LazyNotify(LazyConnector):
    def __init__(self, host='localhost', port=5672):
        super(LazyNotify, self).__init__('notify', host=host, port=port)

    def handle_insert(self, message, users: List[int]):
        # self.publish(dumps({'message': message.to_dict(), 'users': users}, default=str))
        self.publish(dumps('message'))
        # print('handle')


class NotifyListener(Listener):
    def __init__(self, checker: 'Checker', consumer_tag):
        self.checker = checker
        super(NotifyListener, self).__init__('notify', consumer_tag=consumer_tag)

    def callback(self, body: bytes):
        data = loads(body)
        self.checker.add_information(data.get('message', {}), data.get('users', []))
