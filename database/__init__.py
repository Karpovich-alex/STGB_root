from .base import current_session, engine, Middleware, Handler
from .models import User, Message, Bot, Base, Chat, Messengers


def init_db():
    Base.metadata.create_all(engine)
