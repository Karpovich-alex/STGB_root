from json import loads
from typing import Union

import aio_pika

from STGB_backend.WebhookWorker import WebhookWorker
from STGB_backend.checker.update_checker import Updater
from database import Chat, Message
from utils.schema import MultipleNotifyUpdates, WebMessage
from utils.tg_schema import TGMessage


class AIOConnector:
    def __init__(self, queue, host='localhost', port=5672, consumer_tag='listener'):
        self.queue = queue
        self.host = host
        self.port = port
        self.consumer_tag = consumer_tag
        self._channel = None

    async def _publish(self, message: bytes):
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message
            ),
            routing_key=self.queue
        )

    async def publish(self, message: Union[str, bytes]):
        if not self._channel:
            raise AttributeError
        if isinstance(message, str):
            await self._publish(message.encode())
        elif isinstance(message, bytes):
            await self._publish(message)
        else:
            raise AttributeError('message: Union[str, bytes]')
        return True

    async def handle_insert(self, message):
        return await self.publish(message)

    async def start(self):

        connection = await aio_pika.connect_robust(
            f"amqp://guest:guest@{self.host}/"
        )
        # async with connection:
        # Creating channel
        self._channel = await connection.channel()  # type: aio_pika.Channel


class AIOListener:
    def __init__(self, queue, host='localhost', port=5672, consumer_tag='listener'):
        self.queue_name = queue
        self.host = host
        self.port = port
        self.consumer_tag = consumer_tag

    async def _callback(self, body: bytes):
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
                        await self._callback(message.body)


class AIONotifyListener(AIOListener):
    def __init__(self, updater: Updater, **kwargs):
        super().__init__('notify', **kwargs)
        self.updater = updater

    async def _callback(self, body: bytes):
        data = loads(body)

        await self.updater.handle_updates(MultipleNotifyUpdates(**data))


def chat_id_to_messenger(chat_id):
    new_chat_id = Chat.get_messenger_id(chat_id)
    return new_chat_id


class AIOSender(AIOListener):
    def __init__(self, **kwargs):
        self.webhook_worker = WebhookWorker()
        super(AIOSender, self).__init__("send", **kwargs)

    async def _callback(self, body: bytes):
        message = WebMessage.parse_raw(body)
        chat = Chat.get_chat(chat_id=message.chat_id)
        bot = chat.bot
        result = await self.webhook_worker.send_message(bot.token, text=message.text, chat_id=chat.messenger_id)
        update = TGMessage(**result['result'])
        Message.add_message(update, bot=bot)
