# -*- test-case-name: vxtxtalert.tests.test_survey -*-
# -*- coding: utf8 -*-
import hashlib
import json
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import FakeRedis
from vumi.application.base import ApplicationWorker

from vxpolls import PollManager, ResultManager, PollDashboardServer


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

    @inlineCallbacks
    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        # Poll Manager is responsible for iterating over
        # questions and batching them.
        self.pm = PollManager(self.r_server)
        self.poll = self.pm.register(self.poll_id, {
            'questions': self.questions,
            'batch_size': self.batch_size,
        })

        # Dashboard server creates an HTTP API for GeckoBoard based
        # dasbhoards.
        self.dashboard = PollDashboardServer(
            self.poll, self.poll.results_manager, {
                'port': self.dashboard_port,
                'path': self.dashboard_prefix,
                'collection_id': self.poll_id,
                'question': self.questions[0]['copy'],
            })
        yield self.dashboard.startService()

    @inlineCallbacks
    def teardown_application(self):
        yield self.dashboard.stopService()
        self.poll.stop()

    def consume_user_message(self, message):
        participant = self.poll.get_participant(message.user())
        if participant.has_unanswered_question:
            self.on_message(participant, message)
        else:
            self.init_session(participant, message)

    def on_message(self, participant, message):
        # receive a message as part of a live session
        content = message['content']
        last_question = self.poll.get_last_question(participant)
        error_message = self.poll.submit_answer(participant, content)
        if error_message:
            self.reply_to(message, error_message)
        else:
            if self.poll.has_more_questions_for(participant):
                next_question = self.poll.get_next_question(participant)
                self.reply_to(message, self.ask_question(participant, next_question))
            else:
                self.end_session(participant, message)

    def end_session(self, participant, message):
        participant.interactions = 0
        participant.has_unanswered_question = False
        next_question = self.poll.get_next_question(participant)
        if next_question:
            self.reply_to(message, self.batch_completed_response,
                continue_session=False)
            self.poll.save_participant(participant)
        else:
            self.reply_to(message, self.survey_completed_response,
                continue_session=False)
            self.poll.save_participant(participant)
            # Archive for demo purposes so we can redial in and start over.
            self.poll.archive(participant)

    def init_session(self, participant, message):
        # brand new session
        if self.poll.has_more_questions_for(participant):
            next_question = self.poll.get_next_question(participant)
            self.reply_to(message, self.ask_question(participant, next_question))
        else:
            self.end_session(participant, message)

    def ask_question(self, participant, question):
        participant.has_unanswered_question = True
        self.poll.set_last_question(participant, question)
        self.poll.save_participant(participant)
        return question.copy
