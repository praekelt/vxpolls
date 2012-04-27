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
            'week3': [{
                'copy': '1 or 2?',
                'valid_responses': ['1', '2'],
                },
                {
                'copy': '3 or 4?',
                'valid_responses': ['3', '4'],
                },
                {
                'copy': '5 or 6?',
                'valid_responses': ['5', '6'],
                }],
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
    def test_continuation_of_session(self):
        # create the inbound message
        msg = self.mkmsg_in(content='red')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_poll_id('register')
        participant.set_poll_id('register')
        participant.set_poll_id('week0')  # No such poll
        participant.set_poll_id('week1')
        participant.set_poll_id('week1')
        # Need to set last question index only after setting poll
        participant.set_last_question_index(0)
        self.app.pm.save_participant(participant)
        retrieved_participant = self.app.pm.get_participant(msg.user())
        #self.assertEqual(['register', 'week0', 'week1'],
                #retrieved_participant.poll_id_list)
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
        participant.set_poll_id('register')
        participant.set_last_question_index(2)
        self.app.pm.save_participant(participant)
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.registration_completed_response)
        self.assertEvent(response, 'close')

    @inlineCallbacks
    def test_finish_one_poll_then_start_another(self):
        # create the inbound message
        msg = self.mkmsg_in(content='apple')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.has_unanswered_question = True
        participant.set_poll_id('register')
        participant.set_last_question_index(2)
        self.app.pm.save_participant(participant)
        participant = self.app.pm.get_participant(msg.user())
        # send to the app
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertResponse(response, self.app.registration_completed_response)
        self.assertEvent(response, 'close')

        msg = self.mkmsg_in(content='any input')
        yield self.dispatch(msg)
        responses = self.get_dispatched_messages()
        self.assertResponse(responses[-1],
                self.default_questions_dict['week1'][0]['copy'])

        msg = self.mkmsg_in(content='red')
        yield self.dispatch(msg)
        responses = self.get_dispatched_messages()
        self.assertResponse(responses[-1],
                self.default_questions_dict['week1'][1]['copy'])

    @inlineCallbacks
    def test_finish_one_poll_then_start_another(self):
        msg = self.mkmsg_in(content='any input')
        # prime the participant
        participant, poll = self.get_participant_and_poll(msg.user())
        participant.set_poll_id('register')
        participant.set_label('jump_to_poll', 'week3')
        self.app.pm.save_participant(participant)
        participant = self.app.pm.get_participant(msg.user())

        msg = self.mkmsg_in(content='any input')
        yield self.dispatch(msg)
        responses = self.get_dispatched_messages()
        self.assertResponse(responses[-1],
                self.default_questions_dict['week3'][0]['copy'])

        msg = self.mkmsg_in(content='1')
        yield self.dispatch(msg)
        responses = self.get_dispatched_messages()
        self.assertResponse(responses[-1],
                self.default_questions_dict['week3'][1]['copy'])


class LongMultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    poll_id_list = [
            'register',
            'week1',
            'week2',
            'week3',
            'week4',
            'week5',
            'week6',
            'week7',
            'week8',
            'week9',
            'week10',
            ]

    default_questions_dict = {
            'register': [{
                'copy': 'Name?',
                'valid_responses': [],
                },
                {
                'copy': 'Week?',
                'valid_responses': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
                'label': 'jump_to_week',
                },
                {
                'copy': 'SMS?',
                'valid_responses': ['yes', 'no'],
                }],

            'week1': [{
                    'copy': 'Week1 question',
                }],

            'week2': [{
                    'copy': 'Week2 question',
                }],

            'week3': [{
                    'copy': 'Week3 question',
                }],

            'week4': [{
                    'copy': 'Week4 question',
                }],

            'week5': [{
                'copy': 'Ask this once regardless of answer',
                'label': 'ask_once_1',
                'checks': {
                    'not exists': {'ask_once_1': ''}
                    },
                },
                {
                'copy': 'Ask this until answer is yes',
                'valid_responses': ['yes', 'no'],
                'label': 'ask_until_1',
                'checks': {
                    'not equal': {'ask_until_1': 'yes'}
                    },
                },
                {
                'copy': 'Skip week 6?',
                'valid_responses': ['yes', 'no'],
                'label': 'skip_week6',
                }],

            'week6': [{
                    'copy': 'Week6 question',
                }],

            'week7': [{
                'copy': 'Ask this once regardless of answer',
                'label': 'ask_once_1',
                'checks': {
                    'not exists': {'ask_once_1': ''}
                    },
                },
                {
                'copy': '1 or 2?',
                'valid_responses': ['1', '2'],
                },
                {
                'copy': '3 or 4?',
                'valid_responses': ['3', '4'],
                },
                {
                'copy': '5 or 6?',
                'valid_responses': ['5', '6'],
                }],

            'week8': [{
                'copy': 'Ask this until answer is yes',
                'valid_responses': ['yes', 'no'],
                'label': 'ask_until_1',
                'checks': {
                    'not equal': {'ask_until_1': 'yes'}
                    },
                }],

            'week9': [{
                'copy': 'Ask this once regardless of answer',
                'label': 'ask_once_1',
                'checks': {
                    'not exists': {'ask_once_1': ''}
                    },
                },
                {
                'copy': 'Ask this until answer is yes',
                'valid_responses': ['yes', 'no'],
                'label': 'ask_until_1',
                'checks': {
                    'not equal': {'ask_until_1': 'yes'}
                    },
                }],

            'week10': [],
            }

    @inlineCallbacks
    def test_a_series_of_interactions(self):

        inputs_and_expected_response = [
            ('Any input',self.default_questions_dict['register'][0]['copy']),
            ('David',self.default_questions_dict['register'][1]['copy']),
            ('4',self.app.registration_partial_response),
            ('Any input',self.default_questions_dict['register'][2]['copy']),
            ('yes',self.app.registration_completed_response),
            ('Any input',self.default_questions_dict['week4'][0]['copy']),
            ('Any input',self.app.survey_completed_response),
            ('Any input',self.default_questions_dict['week5'][0]['copy']),
            ('answered once',self.default_questions_dict['week5'][1]['copy']),
            ('no',self.app.batch_completed_response),
            ('Any input',self.default_questions_dict['week5'][2]['copy']),
            # try invalid response
            ('qe?',self.default_questions_dict['week5'][2]['copy']),
            # now try valid response
            ('yes',self.app.survey_completed_response),
            # should skip ['week7'][0] --- label: ask_once_1 exists
            ('Any input',self.default_questions_dict['week7'][1]['copy']),
            ('1',self.default_questions_dict['week7'][2]['copy']),
            # try invalid response
            ('5',self.default_questions_dict['week7'][2]['copy']),
            # now try valid response
            ('3',self.app.batch_completed_response),
            ('Any input',self.default_questions_dict['week7'][3]['copy']),
            ('5',self.app.survey_completed_response),
            # will ask ['week8'][0] --- label: ask_until_1 is still not yes
            ('Any input',self.default_questions_dict['week8'][0]['copy']),
            ('yes',self.app.survey_completed_response),
            # week9 should now skip all questions
            ('Any input',self.app.survey_completed_response),
            # and week10 has none
            ('Any input',self.app.survey_completed_response),
            ]

        #print ''
        for io in inputs_and_expected_response:
            msg = self.mkmsg_in(content=io[0])
            yield self.dispatch(msg)
            responses = self.get_dispatched_messages()
            output = responses[-1]['content']
            event = responses[-1].get('session_event')
            #print '\t', io[0], '->', output, '(%s)' % event, '[%s]' % io[1]
            self.assertEqual(output, io[1])

