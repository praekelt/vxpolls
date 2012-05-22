import json
import pprint
from datetime import date, timedelta

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vxpolls.multipoll_example import MultiPollApplication


class BaseMultiPollApplicationTestCase(ApplicationTestCase):

    application_class = MultiPollApplication

    timeout = 1
    poll_id_list = ['REGISTER', 'week1', 'week2', 'week3']
    default_questions_dict = {
            'REGISTER': [{
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


#class MultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    #@inlineCallbacks
    #def test_initial_connect(self):
        #msg = self.mkmsg_in(content=None)
        #yield self.dispatch(msg)
        #[response] = self.get_dispatched_messages()
        #participant, poll = self.get_participant_and_poll(msg.user())
        ## make sure we get the first question as a response
        #self.assertResponse(response,
                        #self.default_questions_dict['REGISTER'][0]['copy'])
        ## the session event should be none so it is expecting
        ## a response
        #self.assertEvent(response, None)
        ## get the participant and check the state after the first interaction
        #next_question = poll.get_next_question(participant)
        #self.assertEqual(next_question.copy,
                        #self.default_questions_dict['REGISTER'][1]['copy'])

    #@inlineCallbacks
    #def test_continuation_of_session(self):
        ## create the inbound message
        #msg = self.mkmsg_in(content='red')
        ## prime the participant
        #participant, poll = self.get_participant_and_poll(msg.user())
        #participant.has_unanswered_question = True
        #participant.set_poll_id('REGISTER')
        #participant.set_poll_id('REGISTER')
        #participant.set_poll_id('week0')  # No such poll
        #participant.set_poll_id('week1')
        #participant.set_poll_id('week1')
        ## Need to set last question index only after setting poll
        #participant.set_last_question_index(0)
        #self.app.pm.save_participant(participant)
        #retrieved_participant = self.app.pm.get_participant(msg.user())
        ##self.assertEqual(['REGISTER', 'week0', 'week1'],
                ##retrieved_participant.poll_id_list)
        ## send to the app
        #yield self.dispatch(msg)
        #[response] = self.get_dispatched_messages()
        ## check we get the next question and that its not a session close event
        #self.assertResponse(response,
                        #self.default_questions_dict['week1'][1]['copy'])
        #self.assertEvent(response, None)

    #@inlineCallbacks
    #def test_end_of_session(self):
        ## create the inbound message
        #msg = self.mkmsg_in(content='apple')
        ## prime the participant
        #participant, poll = self.get_participant_and_poll(msg.user())
        #participant.has_unanswered_question = True
        #participant.set_poll_id('REGISTER')
        #participant.set_last_question_index(2)
        #self.app.pm.save_participant(participant)
        ## send to the app
        #yield self.dispatch(msg)
        #[response] = self.get_dispatched_messages()
        #self.assertResponse(response, self.app.registration_completed_response)
        #self.assertEvent(response, 'close')

    #@inlineCallbacks
    #def test_finish_one_poll_then_start_another(self):
        ## create the inbound message
        #msg = self.mkmsg_in(content='apple')
        ## prime the participant
        #participant, poll = self.get_participant_and_poll(msg.user())
        #participant.has_unanswered_question = True
        #participant.set_poll_id('REGISTER')
        #participant.set_last_question_index(2)
        #self.app.pm.save_participant(participant)
        #participant = self.app.pm.get_participant(msg.user())
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

    #@inlineCallbacks
    #def test_finish_one_poll_then_start_another(self):
        #msg = self.mkmsg_in(content='any input')
        ## prime the participant
        #participant, poll = self.get_participant_and_poll(msg.user())
        #participant.set_poll_id('REGISTER')
        #participant.set_label('jump_to_poll', 'week3')
        #self.app.pm.save_participant(participant)
        #participant = self.app.pm.get_participant(msg.user())

        #msg = self.mkmsg_in(content='any input')
        #yield self.dispatch(msg)
        #responses = self.get_dispatched_messages()
        #self.assertResponse(responses[-1],
                #self.default_questions_dict['week3'][0]['copy'])

        #msg = self.mkmsg_in(content='1')
        #yield self.dispatch(msg)
        #responses = self.get_dispatched_messages()
        #self.assertResponse(responses[-1],
                #self.default_questions_dict['week3'][1]['copy'])


#class LongMultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    #poll_id_list = [
            #'REGISTER',
            #'week1',
            #'week2',
            #'week3',
            #'week4',
            #'week5',
            #'week6',
            #'week7',
            #'week8',
            #'week9',
            #'week10',
            #]

    #default_questions_dict = {
            #'REGISTER': [{
                #'copy': 'Name?',
                #'valid_responses': [],
                #},
                #{
                #'copy': 'Week?',  # Will trigger a jump to week (20 - answer)
                #'valid_responses': ['1', '2', '3', '4', '5',
                                    #'6', '7', '8', '9', '10',
                                    #'11', '12', '13', '14', '15',
                                    #'16', '17', '18', '19', '20'],
                #'label': 'weeks_till',
                #},
                #{
                #'copy': 'SMS?',
                #'valid_responses': ['yes', 'no'],
                #}],

            #'week1': [{
                    #'copy': 'Week1 question',
                #}],

            #'week2': [{
                    #'copy': 'Week2 question',
                #}],

            #'week3': [{
                    #'copy': 'Week3 question',
                #}],

            #'week4': [{
                    #'copy': 'Week4 question',
                #}],

            #'week5': [{
                #'copy': 'Ask this once regardless of answer',
                #'label': 'ask_once_1',
                #'checks': {
                    #'not exists': {'ask_once_1': ''}
                    #},
                #},
                #{
                #'copy': 'Ask this until answer is yes',
                #'valid_responses': ['yes', 'no'],
                #'label': 'ask_until_1',
                #'checks': {
                    #'not equal': {'ask_until_1': 'yes'}
                    #},
                #},
                #{
                #'copy': 'Skip week 6?',
                #'valid_responses': ['yes', 'no'],
                #'label': 'skip_week6',
                #}],

            #'week6': [{
                    #'copy': 'Week6 question',
                #}],

            #'week7': [{
                #'copy': 'Ask this once regardless of answer',
                #'label': 'ask_once_1',
                #'checks': {
                    #'not exists': {'ask_once_1': ''}
                    #},
                #},
                #{
                #'copy': '1 or 2?',
                #'valid_responses': ['1', '2'],
                #},
                #{
                #'copy': '3 or 4?',
                #'valid_responses': ['3', '4'],
                #},
                #{
                #'copy': '5 or 6?',
                #'valid_responses': ['5', '6'],
                #}],

            #'week8': [{
                #'copy': 'Ask this until answer is yes',
                #'valid_responses': ['yes', 'no'],
                #'label': 'ask_until_1',
                #'checks': {
                    #'not equal': {'ask_until_1': 'yes'}
                    #},
                #}],

            #'week9': [{
                #'copy': 'Ask this once regardless of answer',
                #'label': 'ask_once_1',
                #'checks': {
                    #'not exists': {'ask_once_1': ''}
                    #},
                #},
                #{
                #'copy': 'Ask this until answer is yes',
                #'valid_responses': ['yes', 'no'],
                #'label': 'ask_until_1',
                #'checks': {
                    #'not equal': {'ask_until_1': 'yes'}
                    #},
                #}],

            #'week10': [],
            #}

    #@inlineCallbacks
    #def test_a_series_of_interactions(self):

        #inputs_and_expected = [
            #('Any input', self.default_questions_dict['REGISTER'][0]['copy']),
            #('David', self.default_questions_dict['REGISTER'][1]['copy']),
            ## Answering 16 for the next question will trigger a jump to
            ## week (20-16) = week4 using a derived date parameter
            ## saved in the Participant via custom app logic
            #('16', self.app.registration_partial_response),
            #('Any input', self.default_questions_dict['REGISTER'][2]['copy']),
            #('yes', self.app.registration_completed_response),
            #('Any input', self.default_questions_dict['week4'][0]['copy']),
            #('Any input', self.app.survey_completed_response),
            #('Any input', self.default_questions_dict['week5'][0]['copy']),
            #('answered once', self.default_questions_dict['week5'][1]['copy']),
            #('no', self.app.batch_completed_response),
            #('Any input', self.default_questions_dict['week5'][2]['copy']),
            ## try invalid response
            #('qe?', self.default_questions_dict['week5'][2]['copy']),
            ## now try valid response
            #('yes', self.app.survey_completed_response),
            ## should skip ['week7'][0] --- label: ask_once_1 exists
            #('Any input', self.default_questions_dict['week7'][1]['copy']),
            #('1', self.default_questions_dict['week7'][2]['copy']),
            ## try invalid response
            #('5', self.default_questions_dict['week7'][2]['copy']),
            ## now try valid response
            #('3', self.app.batch_completed_response),
            #('Any input', self.default_questions_dict['week7'][3]['copy']),
            #('5', self.app.survey_completed_response),
            ## will ask ['week8'][0] --- label: ask_until_1 is still not yes
            #('Any input', self.default_questions_dict['week8'][0]['copy']),
            #('yes', self.app.survey_completed_response),
            ## week9 should now skip all questions
            #('Any input', self.app.survey_completed_response),
            ## and week10 has none
            #('Any input', self.app.survey_completed_response),
            #]

        #for io in inputs_and_expected:
            #msg = self.mkmsg_in(content=io[0])
            #yield self.dispatch(msg)
            #responses = self.get_dispatched_messages()
            #output = responses[-1]['content']
            #event = responses[-1].get('session_event')
            #self.assertEqual(output, io[1])
        #archived = self.app.pm.get_archive(self.mkmsg_in(content='').user())
        #self.assertEqual(archived[-1].labels.get('expected_date'),
                #(date.today()
                    #+ timedelta(weeks=20
                        #- int(inputs_and_expected[2][0]))).isoformat())


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

    def custom_poll_logic_function(self, participant):
        new_poll = participant.get_label('JUMP_TO_POLL')
        current_poll_id = participant.get_poll_id()
        if new_poll and current_poll_id != 'CUSTOM_POLL_ID_0':
            self.try_go_to_specific_poll(participant, new_poll)
            participant.set_label('JUMP_TO_POLL', None)

    def custom_answer_logic_function(self, participant, answer, poll_question):
        try:
            self.poll_id_map
        except:
            self.poll_id_map = {}
            for i in self.poll_id_list:
                self.poll_id_map[i] = i

        def months_to_week(month):
            m = int(month)
            #m = 1
            week = (m - 1) * 4 + 1
            poll_number = week + 36  # given prev poll set of 5 - 40 + reg
            #print "week", week, "= poll", poll
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
        #print self.poll_id_prefix
        if label_value is not None:
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value == '0':
                participant.set_label('USER_STATUS', '4')
                self.poll_id_list = self.poll_id_list[:1]
            if poll_question.label == 'EXPECTED_MONTH' \
                    and label_value != '0':
                        poll_name = "WEEK%s" % month_of_year_to_week(
                                label_value)[0]
                        print poll_name,
                        poll_id = "%s%s" % (self.poll_id_prefix, month_of_year_to_week(label_value)[1])
                        #poll_id = self.poll_id_map.get(poll_name)
                        participant.set_label('JUMP_TO_POLL', poll_id)
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value == '6':  # max age for demo should be 5
                    #and label_value == '11':
                participant.set_label('USER_STATUS', '5')
                self.poll_id_list = self.poll_id_list[:1]
            if poll_question.label == 'INITIAL_AGE' \
                    and label_value != '6':  # max age for demo should be 5
                    #and label_value != '11':
                        poll_name = "POST%s" % months_to_week(label_value)[0]
                        print poll_name,
                        poll_id =  "%s%s" % (self.poll_id_prefix, months_to_week(label_value)[1])
                        #poll_id = self.poll_id_map.get(poll_name)
                        participant.set_label('JUMP_TO_POLL', poll_id)

    custom_answer_logic = custom_answer_logic_function


class CustomMultiPollApplicationTestCase(BaseMultiPollApplicationTestCase):

    application_class = CustomMultiPollApplication

    @inlineCallbacks
    def setUp(self):
        pig = self.application_class.poll_id_generator(self.poll_id_prefix)
        self.default_questions_dict = {}
        self.default_questions_dict.update(self.register_questions_dict)
        self.rekey_dict(self.register_questions_dict, pig)
        self.default_questions_dict.update(self.make_quizzes("WEEK", 5, 40, pig))
        self.default_questions_dict.update(self.make_quizzes("POST", 1, 20, pig))
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

    poll_id_prefix = "CUSTOM_POLL_ID_"

    gen = CustomMultiPollApplication.poll_id_generator(poll_id_prefix)
    generated_id_list = [gen.next() for i in range(57)]
    print generated_id_list

    poll_id_list = [
            'CUSTOM_POLL_ID_0',
            'WEEK5',
            'WEEK6',
            'WEEK7',
            'WEEK8',
            'WEEK9',
            'WEEK10',
            'WEEK11',
            'WEEK12',
            'WEEK13',
            'WEEK14',
            'WEEK15',
            'WEEK16',
            'WEEK17',
            'WEEK18',
            'WEEK19',
            'WEEK20',
            'WEEK21',
            'WEEK22',
            'WEEK23',
            'WEEK24',
            'WEEK25',
            'WEEK26',
            'WEEK27',
            'WEEK28',
            'WEEK29',
            'WEEK30',
            'WEEK31',
            'WEEK32',
            'WEEK33',
            'WEEK34',
            'WEEK35',
            'WEEK36',
            'WEEK37',
            'WEEK38',
            'WEEK39',
            'WEEK40',
            'POST1',
            'POST2',
            'POST3',
            'POST4',
            'POST5',
            'POST6',
            'POST7',
            'POST8',
            'POST9',
            'POST10',
            'POST11',
            'POST12',
            'POST13',
            'POST14',
            'POST15',
            'POST16',
            'POST17',
            'POST18',
            'POST19',
            'POST20',
            ]
    print len(poll_id_list)
    print len(generated_id_list)
    poll_id_list = generated_id_list

    register_questions_dict = {
            'CUSTOM_POLL_ID_0': [{
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
                'label': '',
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
                'label': '',
                }],
            }

    def rekey_dict(self, dictionary, poll_id_generator):
        new_dict = {}
        for k, v in dictionary.items():
            new_key = poll_id_generator.next()
            #print k, '->', new_key
            new_dict[new_key] = v
        return new_dict

    def make_quizzes(self, prefix, start, finish, poll_id_generator):
        string = "{"
        for i in range(start, finish + 1):
            poll_id = poll_id_generator.next()
            check = int(poll_id[-1:]) % 2
            if check != 0:
                print "%(p)s%(i)s" % {"p": prefix, "i": i},
                print "->", poll_id
                pass
                string = string + """
                "%(poll_id)s": [
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
                    ],""" % {"p": prefix, "i": i, 'poll_id': poll_id}

            else:
                print "%(p)s%(i)s" % {"p": prefix, "i": i},
                print "->", poll_id
                pass
                string = string + """
                "%(poll_id)s": [
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
                    ],""" % {"p": prefix, "i": i, 'poll_id': poll_id}
        string = string[:-1]
        string = string + "\n}"
        return json.loads(string)

    @inlineCallbacks
    def run_inputs(self, inputs_and_expected, do_print=False):
        for io in inputs_and_expected:
            msg = self.mkmsg_in(content=io[0])
            yield self.dispatch(msg)
            responses = self.get_dispatched_messages()
            output = responses[-1]['content']
            event = responses[-1].get('session_event')
            if do_print:
                print "\n>", msg['content'], "\n", output
            self.assertEqual(output, io[1])

    @inlineCallbacks
    def test_register_3(self):
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
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
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
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
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('0', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)
        # Check abortive registration is archived
        archived = self.app.pm.get_archive(self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '4')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_register_2(self):
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
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
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
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
        archived = self.app.pm.get_archive(self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '5')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_full_2_hiv(self):
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('3', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.app.poll_id_prefix, "%s44" %
                                            self.app.poll_id_prefix)
        poll_id = pig.next()
        print "#######################################", poll_id, 
        #poll_id = 'POST9'
        print poll_id, 
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST10'
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
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][7]['copy']),
            ('5', self.default_questions_dict[poll_id][9]['copy']),
            ('1', self.default_questions_dict[poll_id][10]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.app.poll_id_prefix, "%s52" %
                                            self.app.poll_id_prefix)
        poll_id = pig.next()
        #poll_id = 'POST17'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST18'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][6]['copy']),
            ('1', self.default_questions_dict[poll_id][7]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST19'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST20'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('2', self.default_questions_dict[poll_id][2]['copy']),
            ('Any input', self.default_questions_dict[poll_id][6]['copy']),
            ('1', self.default_questions_dict[poll_id][7]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected, False)
        # Check participant is archived
        archived = self.app.pm.get_archive(self.mkmsg_in(content='').user())
        self.assertEqual(archived[-1].labels.get('USER_STATUS'), '2')
        # And confirm re-run is possible
        yield self.run_inputs(inputs_and_expected)

    @inlineCallbacks
    def test_full_1_no_hiv(self):
        pig = self.app.poll_id_generator(self.app.poll_id_prefix)
        poll_id = pig.next()
        inputs_and_expected = [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][3]['copy']),
            ('6', self.default_questions_dict[poll_id][5]['copy']),
            ('2', self.default_questions_dict[poll_id][6]['copy']),
            ('Any input', self.app.registration_completed_response),
            ]

        pig = self.app.poll_id_generator(self.app.poll_id_prefix, "%s32" %
                                            self.app.poll_id_prefix)
        poll_id = pig.next()
        #poll_id = 'WEEK37'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'WEEK38'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'WEEK39'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'WEEK40'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST1'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST2'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST3'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST4'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]

        poll_id = pig.next()
        #poll_id = 'POST5'
        inputs_and_expected = inputs_and_expected + [
            ('Any input', self.default_questions_dict[poll_id][0]['copy']),
            ('1', self.default_questions_dict[poll_id][1]['copy']),
            ('Any input', self.default_questions_dict[poll_id][3]['copy']),
            ('1', self.default_questions_dict[poll_id][4]['copy']),
            ('Any input', self.app.survey_completed_response),
            ]
        yield self.run_inputs(inputs_and_expected)
        #pgen = self.app.poll_id_generator("eee", "eee3")
        #print pgen.next()
        #print pgen.next()
        #print pgen.next()

        #p2g = self.app.poll_id_generator("POST", "POST19")
        #for p in range(2):
            #id = p2g.next()
            #print id, self.app.pm.get(id)

        #print "-------------------------"
        #print self.app.get_next_poll("POST")
        #print self.app.get_next_poll("POST", "POST1")
        #print self.app.get_next_poll("POST", "POST1")
        #print self.app.get_next_poll("POST", "POST19")
        #print self.app.get_next_poll("POST", "POST20")

