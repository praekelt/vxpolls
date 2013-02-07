# -*- test-case-name: tests.test_multipoll_example -*-
# -*- coding: utf8 -*-

from datetime import date, timedelta, datetime

from twisted.internet.defer import inlineCallbacks, returnValue
from vumi.persist.txredis_manager import TxRedisManager

from vxpolls.example import PollApplication
from vxpolls import PollManager


class EventPublisher(object):

    def __init__(self):
        self.subscribers = {}

    @inlineCallbacks
    def send(self, event):
        for subscriber in self.subscribers.get(event.event_type, []):
            yield subscriber(event)

    def subscribe(self, event_type, handler):
        s = self.subscribers.setdefault(event_type, [])
        s.append(handler)


class Event(object):
    def __init__(self, event_type, **data):
        self.event_type = event_type
        self.data = data

    def __getattr__(self, name):
        if name not in self.data:
            raise AttributeError("Event has no attribute %r" % (name,))
        return self.data[name]

    def __eq__(self, other):
        if not isinstance(other, Event):
            return False
        return (self.event_type == other.event_type and
                self.data == other.data)


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
    is_demo = False
    current_date = None

    def validate_config(self):
        self.questions_dict = self.config.get('questions_dict', {})
        self.poll_id_list = self.config.get('poll_id_list',
                                            [self.generate_unique_id()])
        self.r_config = self.config.get('redis_manager', {})
        self.batch_size = self.config.get('batch_size', 9)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_prefix = self.config.get('poll_prefix', 'poll_manager')
        self.poll_name_list = self.config.get('poll_name_list', [])
        self.is_demo = self.config.get('is_demo', False)

    @inlineCallbacks
    def setup_application(self):
        self.event_publisher = EventPublisher()

        self.redis = yield TxRedisManager.from_config(self.r_config)
        self.pm = PollManager(self.redis, self.poll_prefix)
        for poll_id in self.poll_id_list:
            exists = yield self.pm.exists(poll_id)
            if not exists:
                yield self.pm.register(poll_id, {
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
    def get_poll_id_for_number(cls, poll_id_prefix, number):
        return "%s%s" % (poll_id_prefix, number)

    @classmethod
    def get_poll_index(cls, poll_id_prefix, id):
        return int(id[len(poll_id_prefix):])

    @classmethod
    def get_next_poll_id(cls, poll_id_prefix, current_poll=None):
        gen = cls.poll_id_generator(poll_id_prefix, current_poll)
        next_id = gen.next()
        return next_id

    def get_next_poll(self, poll_id_prefix, current_poll=None):
        next_poll = self.pm.get(self.get_next_poll_id(
                                poll_id_prefix, current_poll))
        return next_poll

    @inlineCallbacks
    def get_all_participants(self, poll_id_prefix):
        participants = yield self.pm.active_participants(
                                    self.get_first_poll_id(poll_id_prefix))
        returnValue(participants)

    @inlineCallbacks
    def get_all_registered_participants(self, poll_id_prefix):
        participants = yield self.get_all_participants(poll_id_prefix)
        registered = [p for p in participants if self.is_registered(p)]
        returnValue(registered)

    @inlineCallbacks
    def get_registered_count(self, poll_id_prefix):
        registered = yield self.get_all_registered_participants(poll_id_prefix)
        returnValue(len(registered))

    def is_registered(self, participant):
        """Return True if a participant is registered. False otherwise.

        Sub-classes should override this method. By default participants
        are always considered unregistered.
        """
        return False

    @inlineCallbacks
    def get_participant_count(self, poll_id_prefix):
        participants = yield self.get_all_participants(poll_id_prefix)
        returnValue(len(participants))

    @classmethod
    def make_poll_prefix(cls, other_id):
        return "%s_" % other_id

    @inlineCallbacks
    def reply_to(self, message, response, **kwargs):
        self.event_publisher.send(Event('outbound_message',
                                        message=message))
        yield super(MultiPollApplication, self).reply_to(message,
                                                        response,
                                                        **kwargs)

    @inlineCallbacks
    def consume_user_message(self, message):
        scope_id = message['helper_metadata'].get('poll_id', '')
        participant = yield self.pm.get_participant(scope_id, message.user())

        self.event_publisher.send(Event('inbound_message',
                                        message=message))

        # Even if this is a new user, the Participant record will be
        # initialised on get, so the best check for a new_user is whether
        # the 1st poll has an uid set yet
        current_uid = participant.polls[0].get('uid')
        if current_uid is None:
            # We have a new user
            self.event_publisher.send(Event('new_user',
                                            message=message,
                                            participant=participant))

        # Check whether participant is registered at the start
        is_registered_before = self.is_registered(participant)

        if participant:
            participant.scope_id = scope_id
        yield self.custom_poll_logic_function(participant, message)
        poll_id = participant.get_poll_id()
        if poll_id is None:
            poll_id = self.get_first_poll_id(self.make_poll_prefix(
                                                    participant.scope_id))
        poll = yield self.pm.get_poll_for_participant(poll_id, participant)
        # store the uid so we get this one on the next time around
        # even if the content changes.
        participant.set_poll_id(poll.poll_id)
        participant.set_poll_uid(poll.uid)
        participant.questions_per_session = poll.batch_size
        if participant.has_unanswered_question:
            yield self.on_message(participant, poll, message)
        else:
            yield self.init_session(participant, poll, message)

        # Now we re-examine is_registered() to see if it has changed,
        # and if it has we fire a 'new_registrant' event if needed.
        is_registered_after = self.is_registered(participant)
        if not is_registered_before and is_registered_after:
            self.event_publisher.send(Event('new_registrant',
                                            message=message,
                                            participant=participant))

    @inlineCallbacks
    def on_message(self, participant, poll, message):
        # receive a message as part of a live session
        content = message['content']
        error_message = yield poll.submit_answer(participant, content,
                                            self.custom_answer_logic)
        if error_message:
            yield self.reply_to(message, error_message)
        else:
            if poll.has_more_questions_for(participant):
                next_question = poll.get_next_question(participant)
                question_copy = yield self.ask_question(participant,
                    poll, next_question)
                yield self.reply_to(message, question_copy)
            else:
                yield self.end_session(participant, poll, message)

    @inlineCallbacks
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
            yield self.reply_to(message, batch_completed_response,
                continue_session=False)
            yield self.pm.save_participant(participant)
        else:
            yield self.reply_to(message, survey_completed_response,
                continue_session=False)
            yield self.pm.save_participant(participant.scope_id, participant)
            # Move on to the next poll if possible
            yield self.next_poll_or_archive(participant, poll)

    @inlineCallbacks
    def next_poll_or_archive(self, participant, poll):
        try_next_poll = yield self.try_go_to_next_poll(participant)
        if participant.force_archive or not try_next_poll:
            # Archive for demo purposes so we can redial in and start over.
            if self.is_demo or participant.force_archive:
                yield self.pm.archive(participant.scope_id, participant)

    @inlineCallbacks
    def try_go_to_next_poll(self, participant):
        if not self.is_demo and len(participant.polls) > 1:
            returnValue(False)
        current_poll_id = participant.get_poll_id()
        next_poll_id = self.get_next_poll_id(self.make_poll_prefix(
                                                participant.scope_id),
                                                    current_poll_id)
        next_poll = yield self.pm.get(next_poll_id)
        if next_poll:
            participant.set_poll_id(next_poll_id)
            yield self.pm.save_participant(participant.scope_id, participant)
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def try_go_to_specific_poll(self, participant, poll_id):
        current_poll_id = participant.get_poll_id()
        if poll_id != current_poll_id and self.pm.get(poll_id):
            participant.set_poll_id(poll_id)
            yield self.pm.save_participant(participant.scope_id, participant)
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def ask_question(self, participant, poll, question):
        participant.has_unanswered_question = True
        poll.set_last_question(participant, question)
        yield self.pm.save_participant(participant.scope_id, participant)
        returnValue(question.copy)

    @inlineCallbacks
    def custom_poll_logic_function(self, participant, message):
        # Override custom logic to be called during consume_user_message here

        if self.is_registered(participant):
            # we assume participants who are registered are opted_in
            participant.opted_in = 'True'

        current_poll_id = participant.get_poll_id()
        bdate = participant.get_label("BIRTH_DATE")
        if bdate and current_poll_id != self.get_first_poll_id(
                                                    self.make_poll_prefix(
                                                    participant.scope_id)):
            birth_date = datetime.strptime(bdate, "%Y-%m-%d").date()
            new_poll_number = self.get_poll_number(birth_date)
            current_poll_number = self.get_poll_index(
                            self.make_poll_prefix(participant.scope_id),
                            current_poll_id)
            new_poll_id = self.get_poll_id_for_number(
                            self.make_poll_prefix(participant.scope_id),
                            new_poll_number)
            if new_poll_id != current_poll_id \
                and new_poll_number > current_poll_number:
                yield self.try_go_to_specific_poll(participant, new_poll_id)
                # Fire an event to indicate the user is starting a new poll
                self.event_publisher.send(Event('new_poll',
                                                message=message,
                                                participant=participant,
                                                new_poll_id=new_poll_id))
                participant.has_unanswered_question = False

    def get_current_date(self):
        if self.current_date:  # for testing
            return self.current_date
        else:
            return date.today()

    def get_last_monday(self):
        current_date = self.get_current_date()
        offset = current_date.weekday()
        monday = current_date - timedelta(days=offset)
        return monday

    def get_poll_number(self, birth_date):
        return 36 - (birth_date - self.get_last_monday()).days / 7

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
            week = (m - 1) * 4 + 1
            current_date = self.get_current_date()
            last_monday = self.get_last_monday()
            birth_date = current_date - timedelta(weeks=week)
            poll_number = self.get_poll_number(birth_date)
            return (poll_number, birth_date)

        def month_of_year_to_week(month):
            m = int(month)
            current_date = self.get_current_date()
            present_year = current_date.year
            present_month = current_date.month
            last_monday = self.get_last_monday()
            year_offset = 0
            if m < present_month:
                year_offset = 1
            birth_date = date(present_year + year_offset, m, 15)

            # Revise birth date if too distant
            check_poll_number = self.get_poll_number(birth_date)
            if check_poll_number < 1:
                birth_date = birth_date - timedelta(
                                            weeks=1 - check_poll_number)

            poll_number = self.get_poll_number(birth_date)
            return (poll_number, birth_date)

        label_value = participant.get_label(poll_question.label)
        if participant.get_label('USER_STATUS') == '3':
            participant.force_archive = True
        if label_value is not None:
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value == '13':
                participant.set_label('USER_STATUS', '4')
                participant.force_archive = True
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value != '13':
                        participant.set_label('BIRTH_DATE',
                                str(month_of_year_to_week(label_value)[1]))
                        participant.set_label('REGISTRATION_DATE',
                                str(self.get_current_date()))
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value == '11':
                participant.set_label('USER_STATUS', '5')
                participant.force_archive = True
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value != '11':
                        participant.set_label('BIRTH_DATE',
                                str(months_to_week(label_value)[1]))
                        participant.set_label('REGISTRATION_DATE',
                                str(self.get_current_date()))

    custom_answer_logic = custom_answer_logic_function
