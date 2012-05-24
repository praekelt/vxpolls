import json

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vxpolls.multipoll_example import MultiPollApplication


class BaseMultiPollApplicationTestCase(ApplicationTestCase):

    application_class = MultiPollApplication

    timeout = 2

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


class CustomMultiPollApplication(MultiPollApplication):

    registration_partial_response = 'You have done part of the registration '\
                                    'process, dail in again to complete '\
                                    'your registration.'
    registration_completed_response = 'Thank you.'
    batch_completed_response = 'You have completed the first batch of '\
                                'this weeks questions, dial in again to '\
                                'complete the rest.'
    survey_completed_response = 'You have completed this weeks questions '\
                                'please dial in again next week for more.'


class CustomMultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    application_class = CustomMultiPollApplication

    poll_id_prefix = "CUSTOM_POLL_ID_"

    gen = CustomMultiPollApplication.poll_id_generator(poll_id_prefix)
    poll_id_list = [gen.next() for i in range(57)]

    register_questions = [{
                'copy': "Are you X or do you have Y ?\n" \
                        "1. X\n" \
                        "2. Y\n" \
                        "3. Don't know",
                'valid_responses': ['1', '2', '3'],
                'label': 'USER_STATUS',
                },
                {
                'checks': {'equal': {'USER_STATUS': '3'}},
                'copy': "Follow-up to don't know\n" \
                        "1. More",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '3'}},
                'copy': "Second follow-up to don't know\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "What month is X ?\n" \
                        "1. Jan\n" \
                        "2. Feb\n" \
                        "3. Mar\n" \
                        "4. Apr\n" \
                        "5. May\n" \
                        "6. Jun\n" \
                        "7. Jul\n" \
                        "8. Aug\n" \
                        "9. Sep\n" \
                        "10. Oct\n" \
                        "11. Nov\n" \
                        "12. Dec\n" \
                        "0. Don't Know",
                'valid_responses': ['0', '1', '2', '3', '4', '5', '6',
                                    '7', '8', '9', '10', '11', '12'],
                'label': 'EXPECTED_MONTH',
                },
                {
                'checks': {'equal': {'EXPECTED_MONTH': '0'}},
                'copy': "Please find out ?\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "Do you want Z messages ?\n" \
                        "1. Yes\n" \
                        "2. No",
                'valid_responses': ['1', '2'],
                'label': 'HIV_MESSAGES',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "Thank you, come back later\n" \
                        "1. End",
                'valid_responses': [],
                'label': 'SEND_SMS',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "How many months old Y ?\n" \
                        "1. 1\n" \
                        "2. 2\n" \
                        "3. 3\n" \
                        "4. 4\n" \
                        "5. 5\n" \
                        #"6. 6\n" \
                        #"7. 7\n" \
                        #"8. 8\n" \
                        #"9. 9\n" \
                        #"10. 10\n" \
                        #"11. 11 or more.",
                #'valid_responses': [ '1', '2', '3', '4', '5', '6',
                                    #'7', '8', '9', '10', '11'],
                        "6. 6 or more.",
                'valid_responses': ['1', '2', '3', '4', '5', '6'],
                'label': 'INITIAL_AGE',
                },
                {
                #'checks': {'equal': {'INITIAL_AGE': '11'}},
                'checks': {'equal': {'INITIAL_AGE': '6'}},
                'copy': "Sorry, bye\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "Do you want Z messages ?\n" \
                        "1. Yes\n" \
                        "2. No",
                'valid_responses': ['1', '2'],
                'label': 'HIV_MESSAGES',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "Thank you, come back later\n" \
                        "1. End",
                'valid_responses': [],
                'label': 'SEND_SMS',
                }]

    def make_quiz_list(self, start, finish, poll_id_generator):
        string = "["
        for i in range(start, finish + 1):
            poll_id = poll_id_generator.next()
            check = int(poll_id[-1:]) % 2
            if check != 0:
                string = string + """
                [
                    {
                    "copy": "%(poll_id)s Question 1 ?\\n1. Yes\\n2. No",
                    "valid_responses": [ "1", "2"],
                    "label": "%(poll_id)s_QUESTION_1"
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_1": "1"}},
                    "copy": "%(poll_id)s Question 1 Answer to 1\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_1": "2"}},
                    "copy": "%(poll_id)s Question 1 Answer to 2\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },

                    {
                    "copy": "%(poll_id)s Question 2 ?\\n1. Yes\\n2. No",
                    "valid_responses": [ "1", "2"],
                    "label": "%(poll_id)s_QUESTION_2"
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_2": "1"}},
                    "copy": "%(poll_id)s Question 2 Answer to 1\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_2": "2"}},
                    "copy": "%(poll_id)s Question 2 Answer to 2\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    }
                    ],""" % {'poll_id': poll_id}

            else:
                string = string + """
                [
                    {
                    "copy": "%(poll_id)s Question 1 ?\\n1. Yes\\n2. No",
                    "valid_responses": [ "1", "2"],
                    "label": "%(poll_id)s_QUESTION_1"
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_1": "1"}},
                    "copy": "%(poll_id)s Question 1 Answer to 1\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_1": "2"}},
                    "copy": "%(poll_id)s Question 1 Answer to 2\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },

                    {
                    "checks": {"equal": {"HIV_MESSAGES": "2"}},
                    "copy": "%(poll_id)s Question 2 ?\\n1. Yes\\n2. No",
                    "valid_responses": [ "1", "2"],
                    "label": "%(poll_id)s_QUESTION_2"
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_2": "1"}},
                    "copy": "%(poll_id)s Question 2 Answer to 1\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_2": "2"}},
                    "copy": "%(poll_id)s Question 2 Answer to 2\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },

                    {
                    "checks": {"equal": {"HIV_MESSAGES": "1"}},
                    "copy": "%(poll_id)s Question 3 ?\\n1. Yes\\n2. No",
                    "valid_responses": [ "1", "2"],
                    "label": "%(poll_id)s_QUESTION_3"
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_3": "1"}},
                    "copy": "%(poll_id)s Question 3 Answer to 1\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    },
                    {
                    "checks": {"equal": {"%(poll_id)s_QUESTION_3": "2"}},
                    "copy": "%(poll_id)s Question 3 Answer to 2\\n1. Continue",
                    "valid_responses": [],
                    "label": ""
                    }
                    ],""" % {'poll_id': poll_id}
        string = string[:-1]
        string = string + "\n]"
        return json.loads(string)

    @inlineCallbacks
    def setUp(self):

        # Patch the class to return an instance of FakeRedis for this test
        self.patch(CustomMultiPollApplication, 'get_redis',
            lambda *args: FakeRedis())

        pig = self.application_class.poll_id_generator(self.poll_id_prefix)
        pig.next()  # To skip the id for registration
        other_quizzes_list = self.make_quiz_list(1, 56, pig)

        pig = self.application_class.poll_id_generator(self.poll_id_prefix)
        self.default_questions_dict = {pig.next(): self.register_questions}
        for quiz in other_quizzes_list:
            self.default_questions_dict[pig.next()] = quiz

        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(default_questions_dict)
        #i = 0
        #for k, v in default_questions_dict.iteritems():
            #i = i + len(v)
        #print "QUESTIONS", i

        yield super(BaseMultiPollApplicationTestCase, self).setUp()
        self.config = {
            'poll_id_list': self.poll_id_list,
            'poll_id_prefix': self.poll_id_prefix,
            'questions_dict': self.default_questions_dict,
            'transport_name': self.transport_name,
            'batch_size': 9,
        }
        self.app = yield self.get_application(self.config)

    @inlineCallbacks
    def run_inputs(self, inputs_and_expected, do_print=False):
        for io in inputs_and_expected:
            msg = self.mkmsg_in(content=io[0])
            msg['helper_metadata']['poll_id'] = self.poll_id_prefix[:-1]
            yield self.dispatch(msg)
            responses = self.get_dispatched_messages()
            output = responses[-1]['content']
            event = responses[-1].get('session_event')
            if do_print:
                print "\n>", msg['content'], "\n", output
            self.assertEqual(output, io[1])

    @inlineCallbacks
    def test_register_3(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('3', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_register_1(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('7', self.default_questions_dict[poll_id][5]['copy']),
            ('1', self.default_questions_dict[poll_id][6]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_register_1_dont_know(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('0', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)
        # Check abortive registration is archived
        archived = self.app.pm.get_archive(self.poll_id_prefix[:-1],
                                            self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '4')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_register_2(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('3', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_register_2_too_old(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            #('11', self.default_questions_dict[poll_id][8]['copy']),
            # max age for demo should be 5
            ('6', self.default_questions_dict[poll_id][8]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)
        # Check abortive registration is archived
        archived = self.app.pm.get_archive(self.poll_id_prefix[:-1],
                                            self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '5')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_full_2_hiv(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('3', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.poll_id_prefix, "%s44" %
                                            self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][6]['copy']),
            ('1', self.default_questions_dict[poll_id][7]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected, False)

    @inlineCallbacks
    def test_full_2_hiv_to_archive(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('5', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.poll_id_prefix, "%s52" %
                                            self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][6]['copy']),
            ('1', self.default_questions_dict[poll_id][7]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][6]['copy']),
            ('1', self.default_questions_dict[poll_id][7]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected, False)
        # Check participant is archived
        archived = self.app.pm.get_archive(self.poll_id_prefix[:-1],
                                            self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '2')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_full_1_no_hiv(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('6', self.default_questions_dict[poll_id][5]['copy']),
            ('2', self.default_questions_dict[poll_id][6]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.poll_id_prefix, "%s32" %
                                            self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_full_2_hiv_with_deliberate_555_force_achive(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('3', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.poll_id_prefix, "%s44" %
                                            self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('555', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        yield self.run_inputs(inputs_and_expected)
        # Check participant is archived
        archived = self.app.pm.get_archive(self.poll_id_prefix[:-1],
                                            self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '2')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)


class RegisterMultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    application_class = CustomMultiPollApplication

    poll_id_prefix = "REGISTER_POLL_ID_"

    gen = CustomMultiPollApplication.poll_id_generator(poll_id_prefix)
    poll_id_list = [gen.next() for i in range(1)]

    register_questions = [{
                'copy': "Are you X or do you have Y ?\n" \
                        "1. X\n" \
                        "2. Y\n" \
                        "3. Don't know",
                'valid_responses': ['1', '2', '3'],
                'label': 'USER_STATUS',
                },
                {
                'checks': {'equal': {'USER_STATUS': '3'}},
                'copy': "Follow-up to don't know\n" \
                        "1. More",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '3'}},
                'copy': "Second follow-up to don't know\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "What month is X ?\n" \
                        "1. Jan\n" \
                        "2. Feb\n" \
                        "3. Mar\n" \
                        "4. Apr\n" \
                        "5. May\n" \
                        "6. Jun\n" \
                        "7. Jul\n" \
                        "8. Aug\n" \
                        "9. Sep\n" \
                        "10. Oct\n" \
                        "11. Nov\n" \
                        "12. Dec\n" \
                        "0. Don't Know",
                'valid_responses': ['0', '1', '2', '3', '4', '5', '6',
                                    '7', '8', '9', '10', '11', '12'],
                'label': 'EXPECTED_MONTH',
                },
                {
                'checks': {'equal': {'EXPECTED_MONTH': '0'}},
                'copy': "Please find out ?\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "Do you want Z messages ?\n" \
                        "1. Yes\n" \
                        "2. No",
                'valid_responses': ['1', '2'],
                'label': 'HIV_MESSAGES',
                },
                {
                'checks': {'equal': {'USER_STATUS': '1'}},
                'copy': "Thank you, come back later\n" \
                        "1. End",
                'valid_responses': [],
                'label': 'SEND_SMS',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "How many months old Y ?\n" \
                        "1. 1\n" \
                        "2. 2\n" \
                        "3. 3\n" \
                        "4. 4\n" \
                        "5. 5\n" \
                        #"6. 6\n" \
                        #"7. 7\n" \
                        #"8. 8\n" \
                        #"9. 9\n" \
                        #"10. 10\n" \
                        #"11. 11 or more.",
                #'valid_responses': [ '1', '2', '3', '4', '5', '6',
                                    #'7', '8', '9', '10', '11'],
                        "6. 6 or more.",
                'valid_responses': ['1', '2', '3', '4', '5', '6'],
                'label': 'INITIAL_AGE',
                },
                {
                #'checks': {'equal': {'INITIAL_AGE': '11'}},
                'checks': {'equal': {'INITIAL_AGE': '6'}},
                'copy': "Sorry, bye\n" \
                        "1. End",
                'valid_responses': [],
                'label': '',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "Do you want Z messages ?\n" \
                        "1. Yes\n" \
                        "2. No",
                'valid_responses': ['1', '2'],
                'label': 'HIV_MESSAGES',
                },
                {
                'checks': {'equal': {'USER_STATUS': '2'}},
                'copy': "Thank you, come back later\n" \
                        "1. End",
                'valid_responses': [],
                'label': 'SEND_SMS',
                }]

    @inlineCallbacks
    def setUp(self):

        # Patch the class to return an instance of FakeRedis for this test
        self.patch(CustomMultiPollApplication, 'get_redis',
            lambda *args: FakeRedis())

        pig = self.application_class.poll_id_generator(self.poll_id_prefix)
        self.default_questions_dict = {pig.next(): self.register_questions}

        yield super(BaseMultiPollApplicationTestCase, self).setUp()
        self.config = {
            'poll_id_list': self.poll_id_list,
            'poll_id_prefix': self.poll_id_prefix,
            'questions_dict': self.default_questions_dict,
            'transport_name': self.transport_name,
            'batch_size': 9,
        }
        self.app = yield self.get_application(self.config)

    @inlineCallbacks
    def run_inputs(self, inputs_and_expected, do_print=False):
        for io in inputs_and_expected:
            msg = self.mkmsg_in(content=io[0])
            msg['helper_metadata']['poll_id'] = self.poll_id_prefix[:-1]
            yield self.dispatch(msg)
            responses = self.get_dispatched_messages()
            output = responses[-1]['content']
            event = responses[-1].get('session_event')
            if do_print:
                print "\n>", msg['content'], "\n", output
            self.assertEqual(output, io[1])

    @inlineCallbacks
    def test_register_1_archive_and_repeat(self):
        pig = self.app.poll_id_generator(self.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('7', self.default_questions_dict[poll_id][5]['copy']),
            ('1', self.default_questions_dict[poll_id][6]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)
        # Check participant is archived
        archived = self.app.pm.get_archive(self.poll_id_prefix[:-1],
                                            self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '1')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)
