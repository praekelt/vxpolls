from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vxpolls.example import PollApplication


class BasePollApplicationTestCase(ApplicationTestCase):

    application_class = PollApplication
    timeout = 1
    poll_id = 'poll-id'
    default_questions = [{
            'copy': 'What is your favorite colour?',
            'valid_responses': ['red', 'green', 'blue'],
        },
        {
            'copy': 'Orange, Yellow or Black?',
            'valid_responses': ['orange', 'yellow', 'black'],
        },
        {
            'copy': 'What is your favorite fruit?',
            'valid_responses': ['apple', 'orange'],
        }
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(BasePollApplicationTestCase, self).setUp()
        self.r_server = FakeRedis()
        self.patch(PollApplication, 'get_redis', lambda *a: self.r_server)
        self.config = {
            'poll_id': self.poll_id,
            'questions': self.default_questions,
            'transport_name': self.transport_name,
            'batch_size': 2,
        }
        self.app = yield self.get_application(self.config)

    def get_poll(self, poll_id, participant):
        return self.app.pm.get_poll_for_participant(poll_id, participant)

    def get_participant_and_poll(self, user_id, poll_id=None):
        poll_id = poll_id or self.poll_id
        participant = self.app.pm.get_participant(poll_id, user_id)
        return participant, self.get_poll(poll_id, participant)

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
        [response] = self.get_dispatched_messages()
        participant, poll = self.get_participant_and_poll(msg.user())
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
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(0)
        self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # check we get the next question and that its not a session close event
        self.assertResponse(response, self.default_questions[1]['copy'])
        self.assertEvent(response, None)

    @inlineCallbacks
    def test_end_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        self.app.pm.save_participant(self.poll_id, participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_resume_aborted_session(self):
        # create the inbound init message
        msg = self.mkmsg_in(content=None)
        # prime the participant
        participant = self.app.pm.get_participant(self.poll_id, msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(1)
        self.app.pm.save_participant(self.poll_id, participant)

        # send to app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # check that we get re-asked the original question that
        # we were expecting an answer for when the session aborted
        self.assertResponse(response, self.default_questions[1]['copy'])
        self.assertEvent(response, None)

    @inlineCallbacks
    def test_batching_session(self):
        msg = self.mkmsg_in(content='orange')
        # prime the participant
        participant = self.app.pm.get_participant(self.poll_id, msg.user())
        participant.has_unanswered_question = True
        participant.interactions = 1
        participant.set_last_question_index(1)
        self.app.pm.save_participant(self.poll_id, participant)

        # send to app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
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
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = False
        participant.set_last_question_index(2)
        self.app.pm.save_participant(self.poll_id, participant)
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.survey_completed_response)
        self.assertEvent(response, 'close')


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
        self.app.pm.register(self.poll_id, {
            'questions': self.updated_questions
        })
        msg = self.mkmsg_in(content=None, helper_metadata={
            'poll_id': self.poll_id,
        })
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # make sure we get the first question as a response
        self.assertResponse(response, self.updated_questions[0]['copy'])
        # the session event should be none so it is expecting
        # a response
        self.assertEvent(response, None)
        # get the participant and check the state after the first interaction
        participant, poll = self.get_participant_and_poll(msg.user())
        next_question = poll.get_next_question(participant)
        self.assertEqual(next_question.copy, self.updated_questions[1]['copy'])

    @inlineCallbacks
    def test_storing_of_poll_uid(self):
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.default_questions[0]['copy'])
        participant, poll = self.get_participant_and_poll(msg.user())
        self.assertEqual(participant.get_poll_uid(), poll.uid)

        # update the poll with new content but the system should
        # still remember that we're working with an older version
        # of the poll.
        self.app.pm.register(self.poll_id, {
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
