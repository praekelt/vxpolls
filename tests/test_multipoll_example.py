from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vxpolls.multipoll_example import MultiPollApplication


class BaseMultiPollApplicationTestCase(ApplicationTestCase):

    application_class = MultiPollApplication

    timeout = 1
    poll_id_list = ['register', 'week1', 'week2', 'week3']
    default_questions_dict = {
            'register': [{
                'copy': 'What is your name?',
                'valid_responses': [],
                },
                {
                'copy': 'Orange, Yellow or Black?',
                'valid_responses': ['orange', 'yellow', 'black'],
                },
                {
                'copy': 'What is your favorite fruit?',
                'valid_responses': ['apple', 'orange'],
                }],
            'week1': [{
                'copy': 'Red or blue?',
                'valid_responses': ['red', 'blue'],
                },
                {
                'copy': 'Tall or short?',
                'valid_responses': ['tall', 'short'],
                 }],
            'week2': [],
            'week3': [],
            }

    @inlineCallbacks
    def setUp(self):
        yield super(BaseMultiPollApplicationTestCase, self).setUp()
        self.config = {
            'poll_id_list': self.poll_id_list,
            'questions_dict': self.default_questions_dict,
            'transport_name': self.transport_name,
            'batch_size': 2,
        }
        self.app = yield self.get_application(self.config)

    def get_poll(self, poll_id, participant):
        return self.app.pm.get_poll_for_participant(poll_id, participant)

    def get_participant_and_poll(self, user_id, poll_id=None):
        poll_id = poll_id or (self.poll_id_list + [None])[0]
        participant = self.app.pm.get_participant(user_id)
        return participant, self.get_poll(poll_id, participant)

    def assertResponse(self, response, content):
        self.assertEqual(response['content'], content)

    def assertEvent(self, response, event):
        self.assertEqual(response['session_event'], event)


class MultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    def test_pass(self):
        #print self.__dict__
        pass

    @inlineCallbacks
    def test_initial_connect(self):
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        participant, poll = self.get_participant_and_poll(msg.user())
        # make sure we get the first question as a response
        self.assertResponse(response,
                        self.default_questions_dict['register'][0]['copy'])
        # the session event should be none so it is expecting
        # a response
        self.assertEvent(response, None)
        # get the participant and check the state after the first interaction
        next_question = poll.get_next_question(participant)
        self.assertEqual(next_question.copy,
                        self.default_questions_dict['register'][1]['copy'])

    @inlineCallbacks
    def test_clone_participant(self):
        msg = self.mkmsg_in(content=None)
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.age = 23
        self.assertResponse(response,
                        self.default_questions_dict['register'][0]['copy'])
        self.assertEvent(response, None)
        next_question = poll.get_next_question(participant)
        self.assertEqual(next_question.copy,
                        self.default_questions_dict['register'][1]['copy'])
        clone = self.app.pm.clone_participant(participant, "clone_id")
        self.assertEqual(participant.age, clone.age)
        clone.age = 27
        self.app.pm.save_participant(clone)
        clone = self.app.pm.get_participant("clone_id")
        self.assertEqual(clone.age, 27)
        self.assertEqual(participant.age, 23)



    @inlineCallbacks
    def test_continuation_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='red')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(0)
        participant.set_poll_id('register')
        participant.set_poll_id('register')
        participant.set_poll_id('week0')  # No such poll
        participant.set_poll_id('week1')
        participant.set_poll_id('week1')
        self.app.pm.save_participant(participant)
        retrieved_participant = self.app.pm.get_participant(msg.user())
        self.assertEqual(['register', 'week0', 'week1'],
                retrieved_participant.poll_id_list)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        # check we get the next question and that its not a session close event
        self.assertResponse(response,
                        self.default_questions_dict['week1'][1]['copy'])
        self.assertEvent(response, None)

    @inlineCallbacks
    def test_end_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_last_question_index(2)
        self.app.pm.save_participant(participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.registration_completed_response)
        self.assertEvent(response, 'close')

    #@inlineCallbacks
    #def test_finish_one_poll_then_start_another(self):
        ## create the inbound message
        #msg = self.mkmsg_in(content='apple')
        ## prime the participant
        #participant, poll = self.get_participant_and_poll(msg.user())
        #participant.has_unanswered_question = True
        #participant.set_last_question_index(2)
        #self.app.pm.save_participant(participant)
        ## send to the app
        #yield self.dispatch(msg)
        #[response] = self.get_dispatched_messages()
        #self.assertResponse(response, self.app.registration_completed_response)
        #self.assertEvent(response, 'close')

        #msg = self.mkmsg_in(content='any input')
        #yield self.dispatch(msg)
        #responses = self.get_dispatched_messages()
        #self.assertResponse(responses[-1],
                #self.default_questions_dict['week1'][0]['copy'])

        #msg = self.mkmsg_in(content='red')
        #yield self.dispatch(msg)
        #responses = self.get_dispatched_messages()
        #self.assertResponse(responses[-1],
                #self.default_questions_dict['week1'][1]['copy'])
