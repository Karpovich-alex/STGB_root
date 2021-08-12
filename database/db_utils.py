from config import Config
from utils.connector import LazyNotify
from utils.schema import Update, Message, Chat, MultipleNotifyUpdates

notify = LazyNotify(host=Config.RABBITMQ)


def on_message_add(f):
    def dec(*args, **kwargs):
        message = f(*args, **kwargs)
        update = Update(bot_id=message.get_bot_id(),
                        chats=[Chat(
                            id=message.chat_id,
                            messages=[Message.from_orm(message)],
                            user=message.user
                        )]
                        )

        notify_update = MultipleNotifyUpdates.parse(update=update, users=message.chat.get_users_ids())
        notify.handle_insert(update=notify_update)
        return message

    return dec
