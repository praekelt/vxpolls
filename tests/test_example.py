import yaml

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.utils import ApplicationTestCase

from vxpolls.example import PollApplication


class BasePollApplicationTestCase(ApplicationTestCase):

    application_class = PollApplication
    poll_id = 'poll-id'
    default_questions = [{
            'copy': 'What is your favorite colour?',
            'valid_responses': ['red', 'green', 'blue'],
            'checks': {
                'equal': {
                    'favorite-color': 'None'
                }
            },
            'label': 'red-green-blue',
        },
        {
            'copy': 'Orange, Yellow or Black?',
            'valid_responses': ['orange', 'yellow', 'black'],
            'label': 'orange-yellow-black',
        },
        {
            'copy': 'What is your favorite fruit?',
            'valid_responses': ['apple', 'orange'],
            'label': 'fruit',
        }
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(BasePollApplicationTestCase, self).setUp()
        self.config = {
            'poll_id': self.poll_id,
            'questions': self.default_questions,
            'transport_name': self.transport_name,
            'batch_size': 2,
        }
        self.app = yield self.get_application(self.config)

    @inlineCallbacks
    def get_application(self, *args, **kw):
        app = yield super(BasePollApplicationTestCase, self).get_application(
            *args, **kw)
        self._persist_redis_managers.append(app.redis)
        returnValue(app)

    def get_poll(self, poll_id, participant):
        return self.app.pm.get_poll_for_participant(poll_id, participant)

    @inlineCallbacks
    def get_participant_and_poll(self, user_id, poll_id=None):
        poll_id = poll_id or self.poll_id
        participant = yield self.app.pm.get_participant(poll_id, user_id)
        poll = yield self.get_poll(poll_id, participant)
        returnValue((participant, poll))

    def assertResponse(self, response, content):
        self.assertEqual(response['content'], content)

    def assertEvent(self, response, event):
        self.assertEqual(response['session_event'], event)

    def mkmsg_in(self, **kwargs):
        msg = super(BasePollApplicationTestCase, self).mkmsg_in(**kwargs)
        msg['helper_metadata']['poll_id'] = self.poll_id
        return msg


class PollApplicationTestCase(BasePollApplicationTestCase):

    @inlineCallbacks
    def test_initial_connect(self):
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        participant, poll = yield self.get_participant_and_poll(msg.user())
        # make sure we get the first question as a response
        self.assertResponse(response, self.default_questions[0]['copy'])
        # the session event should be none so it is expecting
        # a response
        self.assertEvent(response, None)
        # get the participant and check the state after the first interaction
        next_question = poll.get_next_question(participant)
        self.assertEqual(next_question.copy, self.default_questions[1]['copy'])

    @inlineCallbacks
    def test_continuation_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='red')
        # prime the participant
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(0)
        yield self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        # check we get the next question and that its not a session close event
        self.assertResponse(response, self.default_questions[1]['copy'])
        self.assertEvent(response, None)

    @inlineCallbacks
    def test_end_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_end_of_session_with_checks(self):
        # create the inbound message
        yield self.app.stopWorker()

        config = self.config.copy()
        config['survey_completed_responses'] = [{
            'copy': 'fruit is apple',
            'checks': [['equal', 'fruit', 'apple']]
        }, {
            'copy': 'fruit is not apple',
            'checks': [['not equal', 'fruit', 'apple']]
        }]

        self.app = yield self.get_application(config)

        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, 'fruit is apple')
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_end_of_session_with_checks_and_fallback(self):
        # create the inbound message
        yield self.app.stopWorker()

        config = self.config.copy()
        # These checks will never pass and so we should fallback to the
        # default survey closing text.
        config['survey_completed_responses'] = [{
            'copy': 'fruit is always false',
            'checks': [['equal', 'fruit', 'not a fruit']]
        }, {
            'copy': 'fruit is never true',
            'checks': [['equal', 'fruit', 'also not a fruit']]
        }]

        yield self.app.pm.register(self.poll_id, config)
        self.app = yield self.get_application(config)

        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, 'You have completed the survey')
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_resume_aborted_session(self):
        # create the inbound init message
        msg = self.mkmsg_in(content=None)
        # prime the participant
        participant = yield self.app.pm.get_participant(
            self.poll_id, msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(1)
        yield self.app.pm.save_participant(self.poll_id, participant)

        # send to app
        yield self.dispatch(msg)
        [response] = yield self.get_dispatched_messages()
        # check that we get re-asked the original question that
        # we were expecting an answer for when the session aborted
        self.assertResponse(response, self.default_questions[1]['copy'])
        self.assertEvent(response, None)

    @inlineCallbacks
    def test_batching_session(self):
        msg = self.mkmsg_in(content='orange')
        # prime the participant
        participant = yield self.app.pm.get_participant(self.poll_id, msg.user())
        participant.has_unanswered_question = True
        participant.interactions = 1
        participant.set_last_question_index(1)
        yield self.app.pm.save_participant(self.poll_id, participant)

        # send to app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        # check we get the batch ended response and session is closed
        self.assertResponse(response, self.app.batch_completed_response)
        self.assertEvent(response, 'close')

        # dial in again
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        last_response = self.get_dispatched_messages()[-1]
        self.assertResponse(last_response, self.default_questions[2]['copy'])
        self.assertEvent(last_response, None)

        msg = self.mkmsg_in(content='orange')
        yield self.dispatch(msg)
        last_response = self.get_dispatched_messages()[-1]
        self.assertResponse(last_response, self.app.survey_completed_response)
        self.assertEvent(last_response, 'close')

    @inlineCallbacks
    def test_initial_connect_after_completion(self):
        msg = self.mkmsg_in(content=None)
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = False
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(self.poll_id, participant)
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_with_primed_state_from_previous_interactions(self):
        msg = self.mkmsg_in(content=None)
        # We're priming the participant to already arrive with data
        # from previous interactions.
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.labels.update({
            'favorite-color': 'red'
        })
        yield self.app.pm.save_participant(self.poll_id, participant)
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # According to the check specified we should arrive straight
        # at question two
        self.assertResponse(response, self.default_questions[1]['copy'])

    @inlineCallbacks
    def test_repeatable_flag(self):
        # create the inbound message
        poll_id = 'non-repeatable-poll'
        msg = self.mkmsg_in(content='apple')
        msg['helper_metadata']['poll_id'] = poll_id
        yield self.app.pm.set(poll_id, {
            'poll_id': poll_id,
            'repeatable': False,
            'questions': self.default_questions,
        })

        # prime the participant
        participant, poll = yield self.get_participant_and_poll(
            msg.user(), poll_id)
        self.assertFalse(poll.repeatable)
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')
        # any follow ups should return the survey completed response
        # as this poll is not repeatable.
        msg_after_close = self.mkmsg_in(content='hello?')
        msg_after_close['helper_metadata']['poll_id'] = poll_id
        yield self.dispatch(msg_after_close)
        [_, last_response] = self.get_dispatched_messages()
        self.assertResponse(last_response, self.app.survey_completed_response)
        self.assertEvent(last_response, 'close')

    @inlineCallbacks
    def test_repeatable_true(self):
        # create the inbound message
        poll_id = 'non-repeatable-poll'
        msg = self.mkmsg_in(content='apple')
        msg['helper_metadata']['poll_id'] = poll_id
        yield self.app.pm.set(poll_id, {
            'poll_id': poll_id,
            'repeatable': True,
            'questions': self.default_questions,
        })

        # prime the participant
        participant, poll = yield self.get_participant_and_poll(
            msg.user(), poll_id)
        self.assertTrue(poll.repeatable)
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')
        # any follow ups should return the first question again
        # as this poll is repeatable.
        msg_after_close = self.mkmsg_in(content='hello?')
        msg_after_close['helper_metadata']['poll_id'] = poll_id
        yield self.dispatch(msg_after_close)
        [_, last_response] = self.get_dispatched_messages()
        self.assertResponse(last_response, self.default_questions[0]['copy'])
        self.assertEvent(last_response, None)

    @inlineCallbacks
    def test_proceed_if_first_submission_valid(self):
        msg = self.mkmsg_in(content='red')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # The first answer sent is a valid response to question 1
        # and so we should get a reply back with question 2
        self.assertResponse(response, self.default_questions[1]['copy'])

    @inlineCallbacks
    def test_archiving_on_end_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = yield self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        yield self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')

        [archive] = yield self.app.pm.get_archive(poll.poll_id,
            participant.user_id)

        self.assertEqual(archive.interactions, 1)
        self.assertEqual(archive.labels, {
            'fruit': 'apple',
            })


class VxpollsRegressionsTestCase(ApplicationTestCase):

    application_class = PollApplication
    poll_id = 'poll-id'

    opt_in_poll = yaml.safe_load("""
        case_sensitive: false
        include_labels: [opted-in]
        poll_id: poll-id
        questions:
        - checks:
          - [not exists, opted-in, '']
          - ['', '', '']
          - ['', '', '']
          copy: Hi and welcome to Afropinions! In order to confirm registration please reply
            with JOIN to 8007
          label: opted-in
          valid_responses: [join, JOIN, Join]
        - checks:
          - ['', '', '']
          - ['', '', '']
          - ['', '', '']
          copy: Thank you! You will need to complete this survey to qualify for the prize
            draw. First tell us, what is your gender? Reply with M for male and F for female.
          label: Gender
          valid_responses: [m, f, male, female, M, F]
        - checks:
          - ['', '', '']
          - ['', '', '']
          - ['', '', '']
          copy: Thank you. Now please tell us, what is your age?
          label: Age
          valid_responses: []
        - checks:
          - ['', '', '']
          - ['', '', '']
          - ['', '', '']
          copy: 'Thank you. One final questions to become a member and qualify for prize draw.
            Please tell us where you live in Kampala? for example: Nakasero'
          label: Locations
          valid_responses: []
        repeatable: true
        survey_completed_response: Welcome! You are now a member of Afropinions. Participation
          is free and confidential. You will be added to the weekly prize draw. Afropinions
          BE HEARD!
    """)

    poll_with_no_input_checks = yaml.safe_load("""
    poll_id: poll-id
    repeatable: true
    survey_completed_response: completed!
    questions:
        - copy: first question
          label: first question
          valid_responses: []
        - copy: second question
          label: second question
          valid_responses: ['yes', 'no']
    """)

    def mkmsg_in(self, **kwargs):
        msg = super(VxpollsRegressionsTestCase, self).mkmsg_in(**kwargs)
        msg['helper_metadata']['poll_id'] = self.poll_id
        return msg

    @inlineCallbacks
    def get_application(self, *args, **kw):
        app = yield super(VxpollsRegressionsTestCase, self).get_application(
            *args, **kw)
        self._persist_redis_managers.append(app.redis)
        returnValue(app)

    @inlineCallbacks
    def get_participant_and_poll(self, user_id, poll_id=None):
        poll_id = poll_id or self.poll_id
        participant = yield self.app.pm.get_participant(poll_id, user_id)
        poll = yield self.get_poll(poll_id, participant)
        returnValue((participant, poll))

    @inlineCallbacks
    def test_sna_opt_in_scenario(self):
        yield self.get_application(self.opt_in_poll)
        yield self.dispatch(self.mkmsg_in(content='join'))
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertTrue('what is your gender' in response['content'])

    @inlineCallbacks
    def test_sna_revisit_after_optin_scenario(self):
        self.app = yield self.get_application(self.opt_in_poll)
        manager = self.app.pm

        msg = self.mkmsg_in(content='hello')
        participant = yield manager.get_participant(self.poll_id, msg.user())
        participant.labels.update({
            'opted-in': 'join'
        })
        yield manager.save_participant(self.poll_id, participant)
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertTrue('what is your gender' in response['content'])

    @inlineCallbacks
    def test_asking_first_question_if_not_valid_input_checks(self):
        app = yield self.get_application(self.poll_with_no_input_checks)
        manager = app.pm

        # check that we're not expecting an answer for this participant
        # which would mean the conversation was server initiated.
        msg = self.mkmsg_in(content=None)
        participant = yield manager.get_participant(self.poll_id, msg.user())
        self.assertFalse(participant.has_unanswered_question)

        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertEqual('first question', response['content'])
        yield self.dispatch(self.mkmsg_in(content='foo'))
        [_, response] = yield self.wait_for_dispatched_messages(2)
        self.assertEqual('second question', response['content'])
        yield self.dispatch(self.mkmsg_in(content='yes'))
        [_, _, response] = yield self.wait_for_dispatched_messages(3)
        self.assertEqual(app.survey_completed_response, response['content'])


class PollManagerVersioningTestCase(BasePollApplicationTestCase):

    # copy the default_questions and change the
    # content of the first one.
    updated_questions = BasePollApplicationTestCase.default_questions[:]
    updated_questions[0] = {
        'copy': 'What is your favorite food?',
        'valid_responses': ['italian', 'mexican', 'asian'],
    }

    @inlineCallbacks
    def test_first_question(self):
        # update the poll with new content
        yield self.app.pm.register(self.poll_id, {
            'questions': self.updated_questions
        })
        msg = self.mkmsg_in(content=None, helper_metadata={
            'poll_id': self.poll_id,
        })
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        # make sure we get the first question as a response
        self.assertResponse(response, self.updated_questions[0]['copy'])
        # the session event should be none so it is expecting
        # a response
        self.assertEvent(response, None)
        # get the participant and check the state after the first interaction
        participant, poll = yield self.get_participant_and_poll(msg.user())
        next_question = poll.get_next_question(participant)
        self.assertEqual(next_question.copy, self.updated_questions[1]['copy'])

    @inlineCallbacks
    def test_storing_of_poll_uid(self):
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        [response] = yield self.wait_for_dispatched_messages(1)
        self.assertResponse(response, self.default_questions[0]['copy'])
        participant, poll = yield self.get_participant_and_poll(msg.user())
        self.assertEqual(participant.get_poll_uid(), poll.uid)

        # update the poll with new content but the system should
        # still remember that we're working with an older version
        # of the poll.
        yield self.app.pm.register(self.poll_id, {
            'questions': self.updated_questions
        })

        yield self.dispatch(self.mkmsg_in(content='red'))
        response = self.get_dispatched_messages()[-1]
        self.assertResponse(response, self.default_questions[1]['copy'])

        # now try from a different number, should get an
        # updated first question.
        yield self.dispatch(self.mkmsg_in(content=None, from_addr='123'))
        response = self.get_dispatched_messages()[-1]
        self.assertResponse(response, self.updated_questions[0]['copy'])
