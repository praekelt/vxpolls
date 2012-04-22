# -*- test-case-name: tests.test_example -*-
# -*- coding: utf8 -*-
import hashlib
import json

from vumi.tests.utils import FakeRedis
from vumi.application.base import ApplicationWorker

from vxpolls import PollManager


class PollApplication(ApplicationWorker):

    batch_completed_response = 'You have completed the first batch of '\
                                'questions, dial in again to complete '\
                                'the full survey.'
    survey_completed_response = 'You have completed the survey'

    def validate_config(self):
        self.questions = self.config.get('questions', [])
        self.r_config = self.config.get('redis_config', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_id = self.config.get('poll_id', self.generate_unique_id())

    def generate_unique_id(self):
        return hashlib.md5(json.dumps(self.config)).hexdigest()

    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        self.pm = PollManager(self.r_server)
        if not self.pm.exists(self.poll_id):
            self.pm.register(self.poll_id, {
                'questions': self.questions,
                'batch_size': self.batch_size,
            })

    def teardown_application(self):
        self.pm.stop()

    def consume_user_message(self, message):
        participant = self.pm.get_participant(message.user())
        poll = self.pm.get_poll_for_participant(self.poll_id, participant)
        # store the uid so we get this one on the next time around
        # even if the content changes.
        participant.set_poll_uid(poll.uid)
        participant.questions_per_session = poll.batch_size
        if participant.has_unanswered_question:
            self.on_message(participant, poll, message)
        else:
            self.init_session(participant, poll, message)

    def on_message(self, participant, poll, message):
        # receive a message as part of a live session
        content = message['content']
        error_message = poll.submit_answer(participant, content)
        if error_message:
            self.reply_to(message, error_message)
        else:
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                self.reply_to(message, self.ask_question(participant, poll, next_question))
            else:
                self.end_session(participant, poll, message)

    def end_session(self, participant, poll, message):
        participant.interactions = 0
        participant.has_unanswered_question = False
        next_question = poll.get_next_question(participant)
        if next_question:
            self.reply_to(message, self.batch_completed_response,
                continue_session=False)
            self.pm.save_participant(participant)
        else:
            self.reply_to(message, self.survey_completed_response,
                continue_session=False)
            self.pm.save_participant(participant)
            # Archive for demo purposes so we can redial in and start over.
            self.pm.archive(participant)

    def init_session(self, participant, poll, message):
        # brand new session
        if poll.has_more_questions_for(participant):
            next_question = poll.get_next_question(participant)
            self.reply_to(message, self.ask_question(participant, poll, next_question))
        else:
            self.end_session(participant, poll, message)

    def ask_question(self, participant, poll, question):
        participant.has_unanswered_question = True
        poll.set_last_question(participant, question)
        self.pm.save_participant(participant)
        return question.copy
