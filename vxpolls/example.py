# -*- test-case-name: tests.test_example -*-
# -*- coding: utf8 -*-
import hashlib
import json

from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue

from vumi.persist.txredis_manager import TxRedisManager
from vumi.application.base import ApplicationWorker

from vxpolls.manager import PollManager, PollQuestion


class PollApplication(ApplicationWorker):

    batch_completed_response = 'You have completed the first batch of '\
                                'questions, dial in again to complete '\
                                'the full survey.'
    survey_completed_response = 'You have completed the survey'

    def validate_config(self):
        self.questions = self.config.get('questions', [])
        self.survey_completed_responses = self.config.get(
            'survey_completed_responses', [])
        self.r_config = self.config.get('redis_manager', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_prefix = self.config.get('poll_prefix', 'poll_manager')
        self.poll_id = self.config.get('poll_id') or self.generate_unique_id()

    def generate_unique_id(self):
        return hashlib.md5(json.dumps(self.config)).hexdigest()

    @inlineCallbacks
    def setup_application(self):
        self.redis = yield TxRedisManager.from_config(self.r_config)
        self.pm = PollManager(self.redis, self.poll_prefix)
        exists = yield self.pm.exists(self.poll_id)
        if not exists:
            yield self.pm.register(self.poll_id, {
                'questions': self.questions,
                'survey_completed_responses': self.survey_completed_responses,
                'batch_size': self.batch_size,
            })

    def teardown_application(self):
        return self.pm.stop()

    @inlineCallbacks
    def consume_user_message(self, message):
        poll_id = message['helper_metadata']['poll_id']
        participant = yield self.pm.get_participant(poll_id, message.user())
        poll = yield self.pm.get_poll_for_participant(poll_id, participant)

        # store the uid so we get this one on the next time around
        # even if the content changes.
        participant.set_poll_uid(poll.uid)
        participant.poll_id = poll_id
        participant.questions_per_session = poll.batch_size

        # If we have an unanswered question then we always need to reply
        # as it's a resuming session.
        if participant.has_unanswered_question:
            yield self.on_message(participant, poll, message)
        else:
            # If we have more questions for the participant, continue otherwise
            # end the session
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                poll.set_last_question(participant, next_question)
                participant.has_unanswered_question = True
                yield self.on_message(participant, poll, message)
            else:
                participant.has_unanswered_question = False
                yield self.end_session(participant, poll, message)

        if participant.poll_id is not None or not poll.repeatable:
            # None indicates the poll has been archived
            yield self.pm.save_participant(poll.poll_id, participant)

    @inlineCallbacks
    def on_message(self, participant, poll, message):
        content = message['content']
        error_message = yield poll.submit_answer(participant, content)
        if error_message:
            yield self.reply_to(message, error_message)
        else:
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                reply = yield self.ask_question(participant, poll, next_question)
                yield self.reply_to(message, reply)
            else:
                yield self.end_session(participant, poll, message)

    @inlineCallbacks
    def end_session(self, participant, poll, message):
        next_question = poll.get_next_question(participant)
        config = yield self.pm.get_config(poll.poll_id)
        if next_question:
            response = config.get('batch_completed_response',
                                    self.batch_completed_response)
            participant.batch_completed()
            yield self.reply_to(message, response, continue_session=False)
        else:
            default_response = config.get('survey_completed_response',
                self.survey_completed_response)
            response = yield self.pm.get_completed_response(participant, poll,
                default_response)
            yield self.reply_to(message, response,
                continue_session=False)

            if poll.repeatable:
                yield self.pm.archive(poll.poll_id, participant)
            participant.poll_completed()

    @inlineCallbacks
    def init_session(self, participant, poll, message):
        # brand new session, send the first question without inspecting
        # the incoming message
        if poll.has_more_questions_for(participant):
            next_question = poll.get_next_question(participant)
            question_copy = yield maybeDeferred(self.ask_question, participant,
                poll, next_question)
            yield self.reply_to(message, question_copy)
        else:
            yield self.end_session(participant, poll, message)

    def ask_question(self, participant, poll, question):
        participant.has_unanswered_question = True
        poll.set_last_question(participant, question)
        return question.copy
