from .models import User, Message, Bot, Base
from .base import current_session, engine, Middleware, Handler


def init_db():
    Base.metadata.create_all(engine)
