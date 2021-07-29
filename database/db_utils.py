from config import Config
from utils.connector import LazyNotify

notify = LazyNotify(host=Config.RABBITMQ)


def on_message_add(f):
    def dec(*args, **kwargs):
        message: 'Message' = f(*args, **kwargs)
        # notify.handle_insert(message, message.chat.get_users_ids())
        return message

    return dec
