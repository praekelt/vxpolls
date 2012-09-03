import random

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.persist.txredis_manager import TxRedisManager

from vxpolls.manager import PollManager


class PollManagerTestCase(TestCase):

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
    }]

    @inlineCallbacks
    def setUp(self):
        r_server = yield TxRedisManager.from_config({
            'FAKE_REDIS': 'yes'
            })
        self.r_server = r_server.sub_manager('vxpolls_test')
        self.poll_manager = PollManager(self.r_server)
        self.poll_id = 'poll-id'
        self.poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions
        })
        self.participant = yield self.poll_manager.get_participant(self.poll_id,
            'user_id')

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()

    def test_key_prefixes(self):
        pm_prefix = self.poll_manager.r_server.get_key_prefix()
        self.assertEqual(pm_prefix, 'vxpolls_test:poll_manager')

        sm_prefix = self.poll_manager.session_manager.redis.get_key_prefix()
        self.assertEqual(sm_prefix, 'vxpolls_test:poll_manager')

        poll_prefix = self.poll.r_server.get_key_prefix()
        self.assertEqual(poll_prefix, 'vxpolls_test:poll_manager:poll')

    @inlineCallbacks
    def test_session_key_prefixes(self):
        yield self.poll_manager.session_manager.create_session(
            "dummy_test_session")
        keys = yield self.r_server._client.keys("*dummy_test_session")
        self.assertEqual(
            "vxpolls_test:poll_manager:session:dummy_test_session", keys[0])

    @inlineCallbacks
    def test_invalid_input_response(self):
        expected_question = 'What is your favorite colour?'
        invalid_input = 'I LOVE TURTLES!!'
        question = self.poll.get_next_question(self.participant)
        self.poll.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield self.poll.submit_answer(self.participant,
                                                    invalid_input)
        self.assertEqual(response, expected_question)

    @inlineCallbacks
    def test_valid_input_response(self):
        expected_question = 'What is your favorite colour?'
        valid_input = 'red'
        question = self.poll.get_next_question(self.participant)
        self.poll.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield self.poll.submit_answer(self.participant,
                                                    valid_input)
        self.assertEqual(None, response)

    @inlineCallbacks
    def test_iterating(self):
        for index, question in enumerate(self.default_questions):
            valid_input = random.choice(question['valid_responses'])
            next_question_copy = question['copy']
            next_question = self.poll.get_next_question(
                                                self.participant)
            self.assertEqual(next_question.copy, next_question_copy)
            last_question = self.poll.get_last_question(
                                                self.participant)
            self.poll.set_last_question(self.participant,
                                                next_question)
            yield self.poll.submit_answer(self.participant,
                                                valid_input)
            if not index:
                self.assertEqual(None, last_question)
            elif index == len(self.default_questions):
                self.assertEqual(None, next_question)

    @inlineCallbacks
    def test_case_insensitivity(self):
        poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions,
            'case_sensitive': False,
        })
        participant = yield self.poll_manager.get_participant(self.poll_id,
            'user_id')

        expected_question = 'What is your favorite colour?'
        valid_input = 'RED'  # capitalized answer but should still pass
        question = poll.get_next_question(participant)
        poll.set_last_question(participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield poll.submit_answer(participant, valid_input)
        self.assertEqual(None, response)

    @inlineCallbacks
    def test_case_sensitivity(self):
        poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions,
            'case_sensitive': True,
        })
        participant = yield self.poll_manager.get_participant(self.poll_id,
            'user_id')

        expected_question = 'What is your favorite colour?'
        valid_input = 'RED'  # capitalized answer but should fail
        question = poll.get_next_question(participant)
        poll.set_last_question(participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield poll.submit_answer(participant, valid_input)
        # original question should be repeated
        self.assertEqual(expected_question, response)


class MultiLevelPollManagerTestCase(TestCase):

    default_questions = [{
        'copy': 'What is your favorite colour?',
        'label': 'favorite colour',
        'valid_responses': ['red', 'green', 'blue'],
    }, {
        'copy': 'What sort of green? Dark or Light?',
        'label': 'sort of green',
        'valid_responses': ['light', 'dark'],
        'checks': {
            'equal': {
                'favorite colour': 'green',
            }
        }
    }, {
        'copy': 'Orange, Yellow or Black?',
        'valid_responses': ['orange', 'yellow', 'black'],
    }, {
        'copy': 'What is your favorite fruit?',
        'label': 'favorite fruit',
        'valid_responses': ['apple', 'orange'],
    }]

    @inlineCallbacks
    def setUp(self):
        self.r_server = yield TxRedisManager.from_config({
            'FAKE_REDIS': 'yes'
            })
        self.poll_manager = PollManager(self.r_server)
        self.poll_id = 'poll-id'
        self.poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions,
        })
        self.participant = yield self.poll_manager.get_participant(self.poll_id,
            'user_id')

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()

    @inlineCallbacks
    def test_checks_skip(self):
        expected_question = 'What is your favorite colour?'
        valid_input = 'red'
        # get the first question
        question = self.poll.get_next_question(self.participant)
        self.assertEqual(question.valid_responses, ['red', 'green', 'blue'])
        self.poll.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield self.poll.submit_answer(self.participant,
                                                    valid_input)
        self.assertEqual(None, response)

        next_question_copy = 'Orange, Yellow or Black?'
        next_question = self.poll.get_next_question(self.participant)
        self.assertEqual(next_question.copy, next_question_copy)

    @inlineCallbacks
    def test_checks_follow_up(self):
        expected_question = 'What is your favorite colour?'
        valid_input = 'green'
        # get the first question
        question = self.poll.get_next_question(self.participant)
        self.assertEqual(question.valid_responses, ['red', 'green', 'blue'])
        self.poll.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = yield self.poll.submit_answer(self.participant,
                                                    valid_input)
        self.assertEqual(None, response)

        next_question_copy = 'What sort of green? Dark or Light?'
        next_question = self.poll.get_next_question(self.participant)
        self.poll.set_last_question(self.participant, next_question)
        self.assertEqual(next_question.copy, next_question_copy)
        response = yield self.poll.submit_answer(self.participant, 'dark')
        self.assertEqual(None, response)

        next_question_copy = 'Orange, Yellow or Black?'
        next_question = self.poll.get_next_question(self.participant)
        self.assertEqual(next_question.copy, next_question_copy)

    @inlineCallbacks
    def test_clone_participant(self):
        self.participant.age = 23
        clone = yield self.poll_manager.clone_participant(self.participant,
                                                    self.poll_id, "clone_id")
        yield self.poll_manager.save_participant(self.poll_id, clone)
        self.assertEqual(self.participant.age, clone.age)
        clone.age = 27
        yield self.poll_manager.save_participant(self.poll_id, clone)
        retrieved_clone = yield self.poll_manager.get_participant(self.poll_id,
                                                                "clone_id")
        self.assertEqual(retrieved_clone.age, 27)
        self.assertEqual(self.participant.age, 23)
