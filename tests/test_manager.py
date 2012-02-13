import random

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import FakeRedis

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

    def setUp(self):
        self.r_server = FakeRedis()
        self.poll_manager = PollManager(self.r_server, self.default_questions)
        self.participant = self.poll_manager.get_participant('user_id')

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()

    def test_invalid_input_response(self):
        expected_question = 'What is your favorite colour?'
        invalid_input = 'I LOVE TURTLES!!'
        question = self.poll_manager.get_next_question(self.participant)
        self.poll_manager.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = self.poll_manager.submit_answer(self.participant,
                                                    invalid_input)
        self.assertEqual(response, '%s is an invalid answer to %s' % (
            invalid_input, expected_question))

    def test_valid_input_response(self):
        expected_question = 'What is your favorite colour?'
        valid_input = 'red'
        question = self.poll_manager.get_next_question(self.participant)
        self.poll_manager.set_last_question(self.participant, question)
        self.assertEqual(question.copy, expected_question)
        response = self.poll_manager.submit_answer(self.participant,
                                                    valid_input)
        self.assertEqual(None, response)

    def test_iterating(self):
        for index, question in enumerate(self.default_questions):
            valid_input = random.choice(question['valid_responses'])
            next_question_copy = question['copy']
            next_question = self.poll_manager.get_next_question(
                                                self.participant)
            self.assertEqual(next_question.copy, next_question_copy)
            last_question = self.poll_manager.get_last_question(
                                                self.participant)
            self.poll_manager.set_last_question(self.participant,
                                                next_question)
            self.poll_manager.submit_answer(self.participant,
                                                valid_input)
            if not index:
                self.assertEqual(None, last_question)
            elif index == len(self.default_questions):
                self.assertEqual(None, next_question)
