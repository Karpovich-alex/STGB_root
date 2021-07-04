import telegram
from json import loads
from typing import Tuple

def parse_data(body: bytes, bot) -> Tuple[telegram.Message, telegram.User]:
    data = loads(body.decode())
    message = telegram.Message.de_json(data['message'], bot)
    user = telegram.User.de_json(data['user'], bot)
    return message, user