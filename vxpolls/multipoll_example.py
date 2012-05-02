# -*- test-case-name: tests.test_multipull_example -*-
# -*- coding: utf8 -*-


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
        self.poll_id_list = self.config.get('poll_id_list',
                                            [self.generate_unique_id()])

    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        self.pm = PollManager(self.r_server)
        if not self.pm.exists(self.poll_id_list):
            for p in self.poll_id_list:
                self.pm.register(p, {
                    'questions': self.questions_dict.get(p, []),
                    'batch_size': self.batch_size,
                    })

    def consume_user_message(self, message):
        participant = self.pm.get_participant(message.user())
        self.update_current_poll(participant)
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
        if poll.poll_id == 'register':
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

    def update_current_poll(self, participant):
        new_poll = participant.get_label('jump_to_poll')
        if new_poll:
            self.try_go_to_specific_poll(participant, new_poll)
            participant.set_label('jump_to_poll', None)

        new_poll = participant.get_label('jump_to_week')
        if new_poll and participant.get_poll_id() != 'register':
            self.try_go_to_specific_poll(participant, 'week%s' % new_poll)
            participant.set_label('jump_to_week', None)

        if participant.get_label('skip_week6') == 'yes' \
            and participant.get_poll_id() == 'week6':
                self.try_go_to_next_poll(participant)

    def custom_answer_logic_function(self, participant, answer, poll_question):
        #print "%s.%s(%s, %s, %s)" % (
                #self,
                #'custom_answer_logic',
                #participant,
                #answer,
                #poll_question)
        pass

    custom_answer_logic = custom_answer_logic_function
