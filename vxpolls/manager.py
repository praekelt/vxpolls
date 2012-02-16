# -*- test-case-name: vxpolls.tests.test_manager -*-
import time
import json

from vumi.application import SessionManager
from vumi import log

from vxpolls.participant import PollParticipant


class PollManager(object):
    def __init__(self, r_server, questions, batch_size=None,
        r_prefix='poll_manager'):
        self.questions = questions
        self.r_server = r_server
        self.r_prefix = r_prefix
        self.batch_size = batch_size
        self.session_manager = SessionManager(self.r_server,
                                                self.r_key('session'))

    def r_key(self, *args):
        parts = [self.r_prefix]
        parts.extend(args)
        return ':'.join(parts)

    def get_participant(self, user_id):
        session_data = self.session_manager.load_session(user_id)
        participant = PollParticipant(user_id, session_data)
        if self.batch_size:
            participant.questions_per_session = self.batch_size
        return participant

    def save_participant(self, participant):
        participant.updated_at = time.time()
        self.session_manager.save_session(participant.user_id,
                                    participant.clean_dump())

    def get_last_question(self, participant):
        index = participant.last_question_index
        if index is not None:
            return self.get_question(index)

    def set_last_question(self, participant, question):
        participant.last_question_index = question.index

    def get_next_question(self, participant):
        last_question = self.get_last_question(participant)
        if last_question:
            next_index = last_question.index + 1
        else:
            next_index = 0
        return self.get_question(next_index)

    def submit_answer(self, participant, answer):
        poll_question = self.get_last_question(participant)
        assert poll_question, 'Need a question to submit an answer for'
        if poll_question.answer(answer):
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

class PollQuestion(object):
    def __init__(self, index, copy, valid_responses=[],
                    send_at=None, group_name=None):
        self.index = index
        self.copy = copy
        self.valid_responses = [unicode(a).lower() for a in valid_responses]
        self.send_at = send_at
        self.group_name = group_name
        self.answered = False

    def answer(self, answer):
        if self.valid_responses and (answer.lower() not in self.valid_responses):
                return False
        else:
            self.answer = answer
            self.answered = True
            return self.answered

    def __repr__(self):
        return '<PollQuestion copy: %s, responses: %s>' % (
            repr(self.copy), repr(self.valid_responses))

