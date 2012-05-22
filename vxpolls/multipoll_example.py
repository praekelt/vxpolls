# -*- test-case-name: tests.test_multipull_example -*-
# -*- coding: utf8 -*-

from datetime import datetime, date, timedelta

from vumi.tests.utils import FakeRedis
#from vumi.application.base import ApplicationWorker
from vxpolls.example import PollApplication

from vxpolls import PollManager


class MultiPollApplication(PollApplication):

    registration_partial_response = 'You have done part of the registration '\
                                    'process, dail in again to complete '\
                                    'your registration.'
    registration_completed_response = 'You have completed registration, '\
                                      'dial in again to start the surveys.'

    batch_completed_response = 'You have completed the first batch of '\
                                'this weeks questions, dial in again to '\
                                'complete the rest.'
    survey_completed_response = 'You have completed this weeks questions '\
                                'please dial in again next week for more.'

    custom_answer_logic = None

    def validate_config(self):
        self.questions_dict = self.config.get('questions_dict', {})
        self.r_config = self.config.get('redis_config', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_prefix = self.config.get('poll_prefix', 'poll_manager')
        #self.poll_id_prefix = "%s_POLL_ID_" % self.poll_prefix
        self.poll_id_prefix = self.config.get('poll_id_prefix', 'POLL_ID_')
        self.poll_id_list = self.config.get('poll_id_list',
                                            [self.generate_unique_id()])
        self.poll_name_list = self.config.get('poll_name_list', [])

    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        self.pm = PollManager(self.r_server, self.poll_prefix)
        for poll_id in self.poll_id_list:
            if not self.pm.exists(poll_id):
                self.pm.register(poll_id, {
                    'questions': self.questions_dict.get(poll_id, []),
                    'batch_size': self.batch_size,
                    })

    @classmethod
    def poll_id_generator(cls, poll_id_prefix, last_id=None):
        num = 0
        if last_id:
            num = int(last_id[len(poll_id_prefix):]) + 1
        while True:
            yield "%s%s" % (poll_id_prefix, num)
            num = num + 1

    @classmethod
    def get_first_poll_id(cls, poll_id_prefix):
        return "%s%s" % (poll_id_prefix, 0)

    @classmethod
    def get_next_poll_id(cls, poll_id_prefix, current_poll=None):
        gen = cls.poll_id_generator(poll_id_prefix, current_poll)
        next_id = gen.next()
        return next_id

    def get_next_poll(self, poll_id_prefix, current_poll=None):
        next_poll = self.pm.get(self.get_next_poll_id(
                                poll_id_prefix, current_poll))
        return next_poll

    def consume_user_message(self, message):
        participant = self.pm.get_participant(message.user())
        self.custom_poll_logic_function(participant)
        poll_id = participant.get_poll_id()
        if poll_id is None:
            poll_id = (self.poll_id_list + [None])[0]
        poll = self.pm.get_poll_for_participant(poll_id, participant)
        # store the uid so we get this one on the next time around
        # even if the content changes.
        participant.set_poll_id(poll.poll_id)
        participant.set_poll_uid(poll.uid)
        participant.questions_per_session = poll.batch_size
        if participant.has_unanswered_question:
            self.on_message(participant, poll, message)
        else:
            self.init_session(participant, poll, message)

    def on_message(self, participant, poll, message):
        # receive a message as part of a live session
        content = message['content']
        error_message = poll.submit_answer(participant, content,
                                            self.custom_answer_logic)
        if error_message:
            self.reply_to(message, error_message)
        else:
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                self.reply_to(message, self.ask_question(participant, poll,
                                                            next_question))
            else:
                self.end_session(participant, poll, message)

    def end_session(self, participant, poll, message):
        first_poll_id = self.get_first_poll_id(self.poll_id_prefix)
        if poll.poll_id == first_poll_id:
            batch_completed_response = self.registration_partial_response
            survey_completed_response = self.registration_completed_response
        else:
            batch_completed_response = self.batch_completed_response
            survey_completed_response = self.survey_completed_response
        participant.interactions = 0
        participant.has_unanswered_question = False
        next_question = poll.get_next_question(participant)
        if next_question:
            self.reply_to(message, batch_completed_response,
                continue_session=False)
            self.pm.save_participant(participant)
        else:
            self.reply_to(message, survey_completed_response,
                continue_session=False)
            self.pm.save_participant(participant)
            # Move on to the next poll if possible
            self.next_poll_or_archive(participant, poll)

    def next_poll_or_archive(self, participant, poll):
        if not self.try_go_to_next_poll(participant):
            # Archive for demo purposes so we can redial in and start over.
            self.pm.archive(participant)

    def try_go_to_next_poll(self, participant):
        current_poll_id = participant.get_poll_id()
        next_poll_id = (self.poll_id_list + [None])[
                                self.poll_id_list.index(current_poll_id) + 1]
        if next_poll_id:
            participant.set_poll_id(next_poll_id)
            self.pm.save_participant(participant)
            return True
        return False

    def try_go_to_specific_poll(self, participant, poll_id):
        current_poll_id = participant.get_poll_id()
        if poll_id in self.poll_id_list and poll_id != current_poll_id:
            participant.set_poll_id(poll_id)
            self.pm.save_participant(participant)
            return True
        return False

    def custom_poll_logic_function(self, participant):
        new_poll = participant.get_label('jump_to_poll')
        if new_poll:
            self.try_go_to_specific_poll(participant, new_poll)
            participant.set_label('jump_to_poll', None)

        def expected_date_to_week(current_week, expected):
            if expected is not None:
                expected = datetime.strptime(expected, "%Y-%m-%d").date()
                today = date.today()
                week_delta = (expected - date.today()).days / 7
                new_week = 'week%s' % week_delta
                if current_week[:4] == 'week' \
                        and int(current_week[4:]) < week_delta:
                    return new_week
            return None

        new_poll = participant.get_label('jump_to_week')
        first_poll_id = self.get_first_poll_id(self.poll_id_prefix)
        if new_poll and participant.get_poll_id() != first_poll_id:
            self.try_go_to_specific_poll(participant, new_poll)
            participant.set_label('jump_to_week', None)

        new_poll = expected_date_to_week(participant.get_poll_id(),
                                        participant.get_label('expected_date'))
        if new_poll:
            self.try_go_to_specific_poll(participant, new_poll)

        if participant.get_label('skip_week6') == 'yes' \
            and participant.get_poll_id() == 'week6':
                self.try_go_to_next_poll(participant)

    def custom_answer_logic_function(self, participant, answer, poll_question):
        label_value = participant.get_label(poll_question.label)
        if label_value is not None:
            if poll_question.label == 'weeks_till':
                participant.set_label(poll_question.label,
                                        'week%s' % answer)
                expected_date = (date.today()
                        + timedelta(weeks=20 - int(answer))).isoformat()
                participant.set_label('expected_date', expected_date)
                participant.set_label('weeks_till', None)

    custom_answer_logic = custom_answer_logic_function
