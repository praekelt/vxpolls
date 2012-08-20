# -*- test-case-name: tests.test_example -*-
# -*- coding: utf8 -*-
import hashlib
import json

from twisted.internet.defer import inlineCallbacks

from vumi.persist.txredis_manager import TxRedisManager
from vumi.application.base import ApplicationWorker

from vxpolls.manager import PollManager


class PollApplication(ApplicationWorker):

    batch_completed_response = 'You have completed the first batch of '\
                                'questions, dial in again to complete '\
                                'the full survey.'
    survey_completed_response = 'You have completed the survey'

    def validate_config(self):
        self.questions = self.config.get('questions', [])
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
        self.r_server = yield TxRedisManager.from_config(self.redis_config)
        self.pm = PollManager(self.r_server, self.poll_prefix)
        if not self.pm.exists(self.poll_id):
            self.pm.register(self.poll_id, {
                'questions': self.questions,
                'batch_size': self.batch_size,
            })

    def teardown_application(self):
        self.pm.stop()

    def consume_user_message(self, message):
        poll_id = message['helper_metadata']['poll_id']
        participant = self.pm.get_participant(poll_id, message.user())
        poll = self.pm.get_poll_for_participant(poll_id, participant)

        # store the uid so we get this one on the next time around
        # even if the content changes.
        participant.set_poll_uid(poll.uid)
        participant.poll_id = poll_id
        participant.questions_per_session = poll.batch_size

        # If we have an unanswered question then we always need to reply
        # as its a resuming session.
        if participant.has_unanswered_question:
            self.on_message(participant, poll, message)
        else:
            # If we have more questions for the participant, continue otherwise
            # end the session
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                participant.has_unanswered_question = True
                poll.set_last_question(participant, next_question)
                self.pm.save_participant(poll.poll_id, participant)
                self.on_message(participant, poll, message)
            else:
                self.end_session(participant, poll, message)

    def on_message(self, participant, poll, message):
        # receive a message as part of a live session
        content = message['content']
        error_message = poll.submit_answer(participant, content)
        if error_message:
            self.reply_to(message, error_message)
        else:
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                reply = self.ask_question(participant, poll, next_question)
                self.reply_to(message, reply)
            else:
                self.end_session(participant, poll, message)

    def end_session(self, participant, poll, message):
        participant.interactions = 0
        participant.has_unanswered_question = False
        next_question = poll.get_next_question(participant)
        config = self.pm.get_config(poll.poll_id)
        if next_question:
            response = config.get('batch_completed_response',
                                    self.batch_completed_response)
            self.reply_to(message, response, continue_session=False)
            self.pm.save_participant(poll.poll_id, participant)
        else:
            response = config.get('survey_completed_response',
                                    self.survey_completed_response)
            self.reply_to(message, response, continue_session=False)
            participant.poll_id = None
            participant.set_poll_uid(None)
            self.pm.save_participant(poll.poll_id, participant)
            if poll.repeatable:
                # Archive for demo purposes so we can redial in and start over.
                self.pm.archive(poll.poll_id, participant)

    def init_session(self, participant, poll, message):
        # brand new session, send the first question without inspecting
        # the incoming message
        if poll.has_more_questions_for(participant):
            next_question = poll.get_next_question(participant)
            self.reply_to(message, self.ask_question(participant, poll, next_question))
        else:
            self.end_session(participant, poll, message)

    def ask_question(self, participant, poll, question):
        participant.has_unanswered_question = True
        poll.set_last_question(participant, question)
        self.pm.save_participant(poll.poll_id, participant)
        return question.copy
