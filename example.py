# -*- test-case-name: vxtxtalert.tests.test_survey -*-
# -*- coding: utf8 -*-
import hashlib
import json
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import FakeRedis
from vumi.application.base import ApplicationWorker

from vxpolls.manager import PollManager


class PollApplication(ApplicationWorker):

    batch_completed_response = 'You have completed the first batch of '\
                                'questions, dial in again to complete '\
                                'the full survey.'
    survey_completed_response = 'You have completed the survey'

    def validate_config(self):
        self.questions = self.config.get('questions', [])
        self.r_config = self.config.get('redis_config', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.poll_id = self.config.get('poll_id', self.generate_unique_id())

    def generate_unique_id(self):
        return hashlib.md5(json.dumps(self.config)).hexdigest()

    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        self.pm = PollManager(self.r_server, self.questions,
                                    batch_size=self.batch_size)

    def teardown_application(self):
        self.pm.stop()

    def consume_user_message(self, message):
        participant = self.pm.get_participant(message.user())
        if participant.has_unanswered_question:
            self.on_message(participant, message)
        else:
            self.init_session(participant, message)

    def on_message(self, participant, message):
        # receive a message as part of a live session
        content = message['content']
        last_question = self.pm.get_last_question(participant)
        error_message = self.pm.submit_answer(participant, content)
        if error_message:
            self.reply_to(message, error_message)
        else:
            if self.pm.has_more_questions_for(participant):
                next_question = self.pm.get_next_question(participant)
                self.reply_to(message, self.ask_question(participant, next_question))
            else:
                self.end_session(participant, message)

    def end_session(self, participant, message):
        participant.interactions = 0
        participant.has_unanswered_question = False
        next_question = self.pm.get_next_question(participant)
        if next_question:
            self.reply_to(message, self.batch_completed_response,
                continue_session=False)
        else:
            self.reply_to(message, self.survey_completed_response,
                continue_session=False)
        self.pm.save_participant(participant)

    def init_session(self, participant, message):
        # brand new session
        if self.pm.has_more_questions_for(participant):
            next_question = self.pm.get_next_question(participant)
            self.reply_to(message, self.ask_question(participant, next_question))
        else:
            self.end_session(participant, message)

    def ask_question(self, participant, question):
        participant.has_unanswered_question = True
        self.pm.set_last_question(participant, question)
        self.pm.save_participant(participant)
        return question.copy
