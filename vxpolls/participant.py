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
        self.has_unanswered_question = False
        self.sent_messages = []
        self.received_messages = []
        self.retries = 0
        self.continue_session = True
        self.polls = [{"poll_id":None, "uid":None, "last_question_index":None}]
        self.labels = {}
        self.force_archive = False
        if session_data:
            self.load(session_data)

    def set_label(self, label, answer):
        self.labels[label] = answer

    def get_label(self, label):
        return self.labels.get(label)

    def get_current_poll(self):
        if len(self.polls) == 0:
            self.append_new_poll(None)
        return self.polls[-1]

    def append_new_poll(self, poll_id, uid=None, last_question_index=None):
        new_poll = {
                "poll_id": poll_id,
                "uid": uid,
                "last_question_index": last_question_index,
                }
        self.polls.append(new_poll)

    def set_last_question_index(self, index):
        self.get_current_poll()['last_question_index'] = index

    def get_last_question_index(self):
        return self.get_current_poll()['last_question_index']

    def set_poll_id(self, id):
        if id != self.get_poll_id():
            if self.get_poll_id() is None:
                self.get_current_poll()['poll_id'] = id
                self.get_current_poll()['uid'] = None
                self.get_current_poll()['last_question_index'] = None
            else:
                self.append_new_poll(id)

    def get_poll_id(self):
        return self.get_current_poll()['poll_id']

    def set_poll_uid(self, uid):
        self.get_current_poll()['uid'] = uid

    def get_poll_uid(self):
        return self.get_current_poll()['uid']

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
            'interactions', int, default=0)
        self.opted_in = typed(session_data,
            'opted_in', lambda v: v == 'True')
        self.age = typed(session_data,
            'age', int)
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
        self.polls = typed(session_data,
            'polls', deserialize, default=[])
        self.labels = typed(session_data,
            'labels', deserialize, default={})
        self.force_archive = typed(session_data,
            'force_archive', lambda v: v == 'True')

    def dump(self):
        return {
            'questions_per_session': self.questions_per_session,
            'interactions': self.interactions,
            'opted_in': self.opted_in,
            'age': self.age,
            'has_unanswered_question': self.has_unanswered_question,
            'updated_at': self.updated_at,
            'sent_messages': serialize_messages(self.sent_messages),
            'received_messages': serialize_messages(self.received_messages),
            'retries': self.retries,
            'polls': serialize(self.polls),
            'labels': serialize(self.labels),
            'force_archive': self.force_archive,
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

    def batch_completed(self):
        self.interactions = 0
        self.has_unanswered_question = False

    def poll_completed(self):
        self.batch_completed()
        self.poll_id = None
        self.set_poll_uid(None)

    def __repr__(self):
        return '<PollParticipant %s, %s, %s>' % (
            self.user_id, self.has_completed_batch(), self.interactions)
