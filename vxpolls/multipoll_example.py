# -*- test-case-name: tests.test_multipoll_example -*-
# -*- coding: utf8 -*-

from datetime import date
import redis

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
        self.poll_id_list = self.config.get('poll_id_list',
                                            [self.generate_unique_id()])
        self.r_config = self.config.get('redis_config', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_prefix = self.config.get('poll_prefix', 'poll_manager')
        self.poll_name_list = self.config.get('poll_name_list', [])

    def setup_application(self):
        self.r_server = self.get_redis(self.r_config)
        self.pm = PollManager(self.r_server, self.poll_prefix)
        for poll_id in self.poll_id_list:
            if not self.pm.exists(poll_id):
                self.pm.register(poll_id, {
                    'questions': self.questions_dict.get(poll_id, []),
                    'batch_size': self.batch_size,
                    })

    def get_redis(self, config):
        return redis.Redis(**self.r_config)

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

    @classmethod
    def make_poll_prefix(cls, other_id):
        return "%s_" % other_id

    def consume_user_message(self, message):
        scope_id = message['helper_metadata'].get('poll_id', '')
        participant = self.pm.get_participant(scope_id, message.user())
        if participant:
            participant.scope_id = scope_id
        self.custom_poll_logic_function(participant)
        poll_id = participant.get_poll_id()
        if poll_id is None:
            poll_id = self.get_first_poll_id(self.make_poll_prefix(
                                                    participant.scope_id))
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
        first_poll_id = self.get_first_poll_id(self.make_poll_prefix(
                                                    participant.scope_id))
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
            self.pm.save_participant(participant.scope_id, participant)
            # Move on to the next poll if possible
            self.next_poll_or_archive(participant, poll)

    def next_poll_or_archive(self, participant, poll):
        if participant.force_archive \
                or not self.try_go_to_next_poll(participant):
            # Archive for demo purposes so we can redial in and start over.
            self.pm.archive(participant.scope_id, participant)

    def try_go_to_next_poll(self, participant):
        current_poll_id = participant.get_poll_id()
        next_poll_id = self.get_next_poll_id(self.make_poll_prefix(
                                                participant.scope_id),
                                                    current_poll_id)
        if self.pm.get(next_poll_id):
            participant.set_poll_id(next_poll_id)
            self.pm.save_participant(participant.scope_id, participant)
            return True
        return False

    def try_go_to_specific_poll(self, participant, poll_id):
        current_poll_id = participant.get_poll_id()
        if poll_id != current_poll_id and self.pm.get(poll_id):
            participant.set_poll_id(poll_id)
            self.pm.save_participant(participant.scope_id, participant)
            return True
        return False

    def ask_question(self, participant, poll, question):
        participant.has_unanswered_question = True
        poll.set_last_question(participant, question)
        self.pm.save_participant(participant.scope_id, participant)
        return question.copy

    def custom_poll_logic_function(self, participant):
        # Override custom logic to be called during consume_user_message here
        new_poll = participant.get_label('JUMP_TO_POLL')
        current_poll_id = participant.get_poll_id()
        if new_poll and current_poll_id != self.get_first_poll_id(
                                                    self.make_poll_prefix(
                                                    participant.scope_id)):
            self.try_go_to_specific_poll(participant, new_poll)
            participant.set_label('JUMP_TO_POLL', None)

    def custom_answer_logic_function(self, participant, answer, poll_question):
        # Override  custom logic to be called during answer handling here

        if poll_question.label == "SEND_SMS":
            #print "SEND SMS TO ->", participant.user_id
            pass

        if str(answer) == '555':
            # Force Archive at end of current Quiz
            # Only works on questions that accept any input
            participant.force_archive = True

        def months_to_week(month):
            m = int(month)
            #m = 1
            week = (m - 1) * 4 + 1
            poll_number = week + 36  # given prev poll set of 5 - 40 + reg
            return (week, poll_number)

        def month_of_year_to_week(month):
            m = int(month)
            current_date = date.today()
            current_date = date(2012, 5, 21)  # For testing
            present_month = current_date.month
            present_day = current_date.day
            month_delta = (m + 12.5 - present_month - present_day / 30.0) % 12
            if month_delta > 8:
                month_delta = 8
            start_week = int(round(40 - month_delta * 4))
            poll_number = start_week - 4
            return (start_week, poll_number)

        label_value = participant.get_label(poll_question.label)
        if label_value is not None:
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value == '13':
                participant.set_label('USER_STATUS', '4')
                participant.force_archive = True
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value != '13':
                        poll_id = "%s%s" % (self.make_poll_prefix(
                                                participant.scope_id),
                                month_of_year_to_week(label_value)[1])
                        participant.set_label('JUMP_TO_POLL', poll_id)
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value == '6':  # max age for demo should be 5
                    #and label_value == '11':
                participant.set_label('USER_STATUS', '5')
                participant.force_archive = True
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value != '6':  # max age for demo should be 5
                    #and label_value != '11':
                        poll_id = "%s%s" % (self.make_poll_prefix(
                                                participant.scope_id),
                                months_to_week(label_value)[1])
                        participant.set_label('JUMP_TO_POLL', poll_id)

    custom_answer_logic = custom_answer_logic_function
