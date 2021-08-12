from .base import current_session, engine, Middleware, Handler
from .models import WebUser, Base, User, Message, Bot, Chat


def init_db():
    Base.metadata.create_all(engine)
