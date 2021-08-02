import datetime
import unittest

from schema import NotifyUpdate, Update, Message, Chat, User


class TestNotifyUpdate(unittest.TestCase):
    def test_append_different(self):
        u = User(uid=1, username='user')
        m = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                    user=u)
        chat = Chat(chat_id=1, messages=[m])
        u1 = Update(bot_id=1, chats=[chat])
        u2 = Update(bot_id=2, chats=[chat])
        nu = NotifyUpdate(user_id=2)
        nu.append(u1)
        nu.append(u2)
        self.assertEqual(nu, NotifyUpdate(user_id=2, updates=[u1, u2]))

    def test_append_to_same(self):
        u = User(uid=1, username='user')
        m = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                    user=u)
        chat1 = Chat(chat_id=1)
        chat2 = Chat(chat_id=2)

        u1 = Update(bot_id=1, chats=[chat1])
        u2 = Update(bot_id=1, chats=[chat2])

        u3 = Update(bot_id=1, chats=[chat1, chat2])
        nu = NotifyUpdate(user_id=2)
        nu.append(u1)
        nu.append(u2)
        self.assertEqual(nu, NotifyUpdate(user_id=2, updates=[u3]))


class TestUpdate(unittest.TestCase):

    def test_append_one_chat(self):
        u = User(uid=2, username='user')
        m = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                    user=u)
        chat = Chat(chat_id=1, messages=[m])
        u = Update(bot_id=1)
        u.append(chat)
        self.assertEqual(u, Update(bot_id=1, chats=[chat]))

    def test_append_chats(self):
        u = User(uid=1, username='user')
        m1 = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        m2 = Message(id=2, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        ch1 = Chat(chat_id=1, messages=[m1])
        ch2 = Chat(chat_id=2, messages=[m2])
        u = Update(bot_id=1)
        u.append(ch1)
        u.append(ch2)
        self.assertEqual(u, Update(bot_id=1, chats=[ch1, ch2]))

    def test_append_to_one_chat(self):
        u = User(uid=2, username='user')
        m1 = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        m2 = Message(id=2, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        ch1 = Chat(chat_id=1, messages=[m1])
        ch2 = Chat(chat_id=1, messages=[m2])
        u = Update(bot_id=1)
        u.append(ch1)
        u.append(ch2)
        ch3 = Chat(chat_id=1, messages=[m1, m2])
        self.assertEqual(u, Update(bot_id=1, chats=[ch3]))


class TestChat(unittest.TestCase):
    def test_append_message(self):
        u = User(uid=1, username='user')
        m1 = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        chat = Chat(chat_id=1)
        chat.append(m1)
        self.assertEqual(chat, Chat(chat_id=1, messages=[m1]))

    def test_append_list(self):
        u = User(uid=1, username='user')
        m1 = Message(id=1, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        m2 = Message(id=2, text='text', time=datetime.datetime(2021, 1, 1, 1, 1, 31),
                     user=u)
        chat = Chat(chat_id=1)
        chat.append([m1, m2])
        self.assertEqual(chat, Chat(chat_id=1, messages=[m1, m2]))
