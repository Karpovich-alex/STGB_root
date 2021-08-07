from json import loads

import aio_pika

from STGB_backend.checker.update_checker import Updater
from utils.schema import MultipleNotifyUpdates


class AIOListener:
    def __init__(self, queue, host='localhost', port=5672, consumer_tag='listener'):
        self.queue_name = queue
        self.host = host
        self.port = port
        self.consumer_tag = consumer_tag

    def _callback(self, message: bytes):
        pass

    async def start(self):
        connection = await aio_pika.connect_robust(
            f"amqp://guest:guest@{self.host}/"
        )
        async with connection:
            # Creating channel
            channel = await connection.channel()  # type: aio_pika.Channel

            # Declaring queue
            queue = await channel.declare_queue(
                self.queue_name,
                durable=True,
                arguments={'consumer_tag': self.consumer_tag, 'prefetch_count': 1}
            )  # type: aio_pika.Queue

            async with queue.iterator() as queue_iter:
                # Cancel consuming after __aexit__
                async for message in queue_iter:
                    async with message.process():
                        self._callback(message.body)


class AIONotifyListener(AIOListener):
    def __init__(self, updater: Updater, **kwargs):
        super().__init__('notify', **kwargs)
        self.updater = updater

    def _callback(self, body: bytes):
        data = loads(body)

        self.updater.handle_updates(MultipleNotifyUpdates(**data))
