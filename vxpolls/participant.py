import time
import json
from vumi.message import TransportUserMessage


def typed(dictionary, key, formatter, default=None):
    value = dictionary.get(key)
    if value is not None:
        return formatter(value)
    return default


def deserialize_messages(json_data):
    message_json_data = json.loads(json_data)
    return [TransportUserMessage.from_json(data) for data in message_json_data]


def serialize_messages(messages):
    return json.dumps([message.to_json() for message in messages])


def deserialize(json_data):
    return json.loads(json_data)


def serialize(data):
    return json.dumps(data)


class PollParticipant(object):

    def __init__(self, user_id, session_data=None):
        self.user_id = user_id
        self.updated_at = time.time()
        self.questions_per_session = None
        self.interactions = 0
        self.opted_in = False
        self.age = None
        self.last_question_index_list = []
        self.has_unanswered_question = False
        self.sent_messages = []
        self.received_messages = []
        self.retries = 0
        self.continue_session = True
        self.poll_id_list = []
        self.poll_uid_list = []
        if session_data:
            self.load(session_data)

    def set_last_question_index(self, index):
        #if index != self.get_last_question_index():
        self.last_question_index_list.append(index)

    def get_last_question_index(self):
        return ([None] + self.last_question_index_list)[-1]

    def set_poll_id(self, id):
        if id != self.get_poll_id():
            if len(self.poll_id_list) and self.poll_id_list[-1] is None:
                self.poll_id_list[-1] = id
            else:
                self.poll_id_list.append(id)

    def get_poll_id(self):
        return ([None] + self.poll_id_list)[-1]

    def set_poll_uid(self, uid):
        if uid != self.get_poll_uid():
            if len(self.poll_uid_list) and self.poll_uid_list[-1] is None:
                self.poll_uid_list[-1] = uid
            else:
                self.poll_uid_list.append(uid)

    def get_poll_uid(self):
        return ([None] + self.poll_uid_list)[-1]

    def __eq__(self, other):
        if isinstance(other, PollParticipant):
            return (self.received_messages == other.received_messages) and \
                (self.sent_messages == other.sent_messages)
        return False

    def add_sent_message(self, message):
        self.sent_messages.append(message)

    def add_received_message(self, message):
        self.received_messages.append(message)

    def last_sent_message(self):
        return self.sent_messages[-1]

    def last_received_message(self):
        return self.received_messages[-1]

    def load(self, session_data):
        self.questions_per_session = typed(session_data,
            'questions_per_session', int)
        self.interactions = typed(session_data,
            'interactions', int)
        self.opted_in = typed(session_data,
            'opted_in', lambda v: v == 'True')
        self.age = typed(session_data,
            'age', int)
        self.last_question_index_list = typed(session_data,
            'last_question_index_list', deserialize, default=[])
        self.has_unanswered_question = typed(session_data,
            'has_unanswered_question', lambda v: v == 'True')
        self.updated_at = typed(session_data,
            'updated_at', float)
        self.sent_messages = typed(session_data,
            'sent_messages', deserialize_messages, default=[])
        self.received_messages = typed(session_data,
            'received_messages', deserialize_messages, default=[])
        self.retries = typed(session_data,
            'retries', int, 0)
        self.poll_uid_list = typed(session_data,
            'poll_uid_list', deserialize, default=[])
        self.poll_id_list = typed(session_data,
            'poll_id_list', deserialize, default=[])

    def dump(self):
        return {
            'questions_per_session': self.questions_per_session,
            'interactions': self.interactions,
            'opted_in': self.opted_in,
            'age': self.age,
            'last_question_index_list': serialize(
                                            self.last_question_index_list),
            'has_unanswered_question': self.has_unanswered_question,
            'updated_at': self.updated_at,
            'sent_messages': serialize_messages(self.sent_messages),
            'received_messages': serialize_messages(self.received_messages),
            'retries': self.retries,
            'poll_uid_list': serialize(self.poll_uid_list),
            'poll_id_list': serialize(self.poll_id_list),
        }

    def clean_dump(self):
        raw_data = self.dump().items()
        return dict([(key, value) for key, value in raw_data
                            if value is not None])

    def has_completed_batch(self):
        return self.interactions >= self.questions_per_session

    def has_remaining_interactions(self):
        if self.questions_per_session:
            return self.questions_per_session > self.interactions
        return True

    def remaining_interactions(self):
        return self.questions_per_session - self.interactions

    def __repr__(self):
        return '<PollParticipant %s, %s, %s>' % (
            self.user_id, self.has_completed_batch(), self.interactions)
