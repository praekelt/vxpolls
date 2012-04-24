# -*- test-case-name: tests.test_manager -*-
import time
import json
import hashlib

from vumi.application import SessionManager
from vumi import log

from vxpolls.participant import PollParticipant
from vxpolls.results import ResultManager


class PollManager(object):
    def __init__(self, r_server, r_prefix='poll_manager'):
        self.r_server = r_server
        self.r_prefix = r_prefix
        self.session_manager = SessionManager(self.r_server,
                                                self.r_key('session'))

    def r_key(self, *args):
        parts = [self.r_prefix]
        parts.extend(args)
        return ':'.join(map(unicode, parts))

    def generate_unique_id(self, version):
        return hashlib.md5(json.dumps(version)).hexdigest()

    def exists(self, poll_id):
        key = self.r_key('versions', poll_id)
        return self.r_server.exists(key)

    def set(self, poll_id, version):
        uid = self.generate_unique_id(version)
        self.r_server.hset(self.r_key('versions', poll_id), uid,
                            json.dumps(version))
        key = self.r_key('version_timestamps', poll_id)
        self.r_server.zadd(key, **{
            uid: time.time(),
        })
        return uid

    def register(self, poll_id, version):
        return self.get(poll_id, uid=self.set(poll_id, version))

    def get(self, poll_id, uid=None):
        versions_key = self.r_key('versions', poll_id)
        timestamps_key = self.r_key('version_timestamps', poll_id)
        uids = self.r_server.zrange(timestamps_key, 0, -1, desc=True)
        uid = uid or uids[0]
        version = json.loads(self.r_server.hget(versions_key, uid))
        return Poll(self.r_server, poll_id, uid, version['questions'],
                version.get('batch_size'), r_prefix=self.r_key('poll'))

    def get_participant(self, user_id):
        session_data = self.session_manager.load_session(user_id)
        participant = PollParticipant(user_id, session_data)
        return participant

    def get_poll_for_participant(self, poll_id, participant):
        #print poll_id
        return self.get(poll_id, participant.get_poll_uid())

    def save_participant(self, participant):
        participant.updated_at = time.time()
        self.session_manager.save_session(participant.user_id,
                                    participant.clean_dump())

    def clone_participant(self, participant, new_id):
        participant.updated_at = time.time()
        self.session_manager.save_session(new_id,
                                    participant.clean_dump())
        return self.get_participant(new_id)

    def active_participants(self):
        return [PollParticipant(user_id, session) for user_id, session
                 in self.session_manager.active_sessions()]

    def inactive_participant_user_ids(self):
        archive_key = self.r_key('archive')
        return self.r_server.smembers(archive_key)

    def archive(self, participant):
        user_id = participant.user_id
        archive_key = self.r_key('archive')
        self.r_server.sadd(archive_key, user_id)

        session_archive_key = self.r_key('session_archive', user_id)
        self.r_server.zadd(session_archive_key, **{
            json.dumps(participant.clean_dump()): participant.updated_at,
        })
        self.session_manager.clear_session(user_id)

    def get_all_archives(self):
        for user_id in self.inactive_participant_user_ids():
            yield self.get_archive(user_id)

    def get_archive(self, user_id):
        archive_key = self.r_key('session_archive', user_id)
        archived_sessions = self.r_server.zrange(archive_key, 0, -1,
                                                    desc=True)
        return [PollParticipant(user_id, json.loads(data)) for
                    data in archived_sessions]

    def stop(self):
        self.session_manager.stop()


class Poll(object):
    def __init__(self, r_server, poll_id, uid, questions, batch_size=None,
        r_prefix='poll'):
        #print "Poll __init__"
        self.r_server = r_server
        self.poll_id = poll_id
        self.uid = uid
        self.questions = questions
        self.r_prefix = r_prefix
        self.batch_size = batch_size
        # Result Manager keeps track of what was answered
        # to which question. We need to tell it about the options
        # before hand.
        self.results_manager = ResultManager(self.r_server,
                                                self.r_key('results'))
        self.results_manager.register_collection(self.poll_id)
        for index, question_data in enumerate(self.questions):
            question = PollQuestion(index, **question_data)
            self.results_manager.register_question(self.poll_id,
                question.label, question.valid_responses)

    def r_key(self, *args):
        parts = [self.r_prefix]
        parts.extend(args)
        return ':'.join(parts)

    def get_last_question(self, participant):
        index = participant.get_last_question_index()
        if index is not None:
            return self.get_question(index)

    def set_last_question(self, participant, question):
        participant.set_last_question_index(question.index)

    def get_next_question(self, participant, last_index=None):
        if last_index is None:
            last_question = self.get_last_question(participant)
        else:
            last_question = self.get_question(last_index)

        if last_question:
            next_index = last_question.index + 1
        else:
            next_index = 0
        question = self.get_question(next_index)
        if question:
            if self.is_suitable_question(participant, question):
                return question
            else:
                return self.get_next_question(participant, next_index)

    def is_suitable_question(self, participant, question):

        state = self.results_manager.get_user(self.poll_id,
                        participant.user_id)

        def equals(key, value):
            return unicode(state[key]) == unicode(value)

        operations_dispatcher = {
            'equal': equals
        }

        if not question.checks:
            return True

        for operation, params in question.checks.items():
            handler = operations_dispatcher[operation]
            key = params.keys()[0]
            value = params.values()[0]
            if handler(key, value):
                return True

        return False

    def submit_answer(self, participant, answer):
        poll_question = self.get_last_question(participant)
        assert poll_question, 'Need a question to submit an answer for'
        if poll_question.answer(answer):
            self.results_manager.add_result(self.poll_id, participant.user_id,
                poll_question.label, answer)
            participant.has_unanswered_question = False
            participant.interactions += 1
        else:
            return poll_question.copy

    def has_more_questions_for(self, participant):
        next_question = self.get_next_question(participant)
        return next_question and participant.has_remaining_interactions()

    def has_question(self, index):
        return self.questions and index < len(self.questions)

    def get_question(self, index):
        if self.has_question(index):
            return PollQuestion(index, **self.questions[index])
        return None


class PollQuestion(object):
    def __init__(self, index, copy, label=None, valid_responses=[], checks={}):
        self.index = index
        self.copy = copy
        self.label = label or copy
        self.valid_responses = [unicode(a) for a in valid_responses]
        self.checks = checks
        self.answered = False

    def answer(self, answer):
        if self.valid_responses and (answer not in self.valid_responses):
            return False
        else:
            self.answer = answer
            self.answered = True
            return self.answered

    def __repr__(self):
        return '<PollQuestion copy: %s, responses: %s>' % (
            repr(self.copy), repr(self.valid_responses))
