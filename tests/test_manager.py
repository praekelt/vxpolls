import random
from datetime import datetime

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.utils import PersistenceMixin

from vxpolls.manager import PollManager


class PollManagerTestCase(PersistenceMixin, TestCase):

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
        yield self._persist_setUp()
        self.redis = yield self.get_redis_manager()
        self.poll_manager = PollManager(self.redis)
        self.poll_id = 'poll-id'
        self.poll = yield self.mkpoll(self.poll_id, {
            'questions': self.default_questions
        })
        self.participant = yield self.poll_manager.get_participant(
            self.poll_id, 'user_id')
        self.key_prefix = "%s:poll_manager" % (
            self._persist_config['redis_manager']['key_prefix'],)

    def mkpoll(self, poll_id, config):
        return self.poll_manager.register(poll_id, config)

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()
        yield self._persist_tearDown()

    @inlineCallbacks
    def test_session_key_prefixes(self):
        session_manager = self.poll_manager.session_manager
        actual_prefix = session_manager.redis.get_key_prefix()
        self.assertEqual(actual_prefix, self.key_prefix)
        yield session_manager.create_session("dummy_test_session")
        keys = yield self.redis._client.keys("*dummy_test_session")
        self.assertEqual("%s:session:dummy_test_session" % (
                self.key_prefix), keys[0])

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
    def complete_poll(self, poll, participant):
        for index, question in enumerate(poll.questions):
            valid_input = random.choice(question['valid_responses'])
            next_question_copy = question['copy']
            next_question = poll.get_next_question(participant)
            self.assertEqual(next_question.copy, next_question_copy)
            last_question = poll.get_last_question(participant)
            poll.set_last_question(participant, next_question)
            yield poll.submit_answer(participant, valid_input)
            if not index:
                self.assertEqual(None, last_question)
            elif index == len(poll.questions):
                self.assertEqual(None, next_question)

    def test_iterating(self):
        return self.complete_poll(self.poll, self.participant)

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
        question = yield poll.get_next_question(participant)
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

    @inlineCallbacks
    def mkpoll_for_export(self, questions=None):
        if questions is None:
            questions = self.default_questions[:]
            for index, question in enumerate(questions):
                question['label'] = 'question-%s' % (index,)

        poll = yield self.mkpoll('export-data-poll', {
            'questions': questions,
            })

        def mkparticipant(user_id):
            return self.poll_manager.get_participant(poll.poll_id, user_id)

        participant1 = yield mkparticipant('user-1')
        participant2 = yield mkparticipant('user-2')
        participant3 = yield mkparticipant('user-3')

        yield self.complete_poll(poll, participant1)
        yield self.complete_poll(poll, participant2)
        yield self.complete_poll(poll, participant3)
        returnValue(poll)

    @inlineCallbacks
    def test_export_user_data(self):
        poll = yield self.mkpoll_for_export()
        user_data = (yield self.poll_manager.export_user_data(poll))
        self.assertTrue(len(user_data), 3)
        for user_id, data in user_data:
            self.assertEqual(
                set(['question-0', 'question-1',
                        'question-2', 'user_timestamp']),
                set(data.keys()))

    @inlineCallbacks
    def test_export_user_data_without_timestamp(self):
        poll = yield self.mkpoll_for_export()
        user_data = (yield self.poll_manager.export_user_data(poll,
            include_timestamp=False))
        for user_id, data in user_data:
            self.assertTrue('user_timestamp' not in data)

    @inlineCallbacks
    def test_export_user_data_respecting_existing_timestamp(self):
        poll = yield self.mkpoll_for_export(questions=[
            {
                'copy': 'question 1',
                'label': 'user_timestamp',
                'valid_responses': ['response'],
            },
            {
                'copy': 'question 2',
                'label': 'some other field',
                'valid_responses': ['response'],
            },
        ])
        user_data = (yield self.poll_manager.export_user_data(poll))
        for user_id, data in user_data:
            self.assertTrue('user_timestamp' in data)
            self.assertEqual(data['user_timestamp'], 'response')

    @inlineCallbacks
    def test_export_user_data_with_old_questions(self):
        poll = yield self.mkpoll_for_export()
        # remove some questions from the poll
        del poll.questions[1:]
        user_data = yield self.poll_manager.export_user_data(
            poll, include_old_questions=True)
        for user_id, data in user_data:
            self.assertEqual(
                set(['question-0', 'question-1',
                     'question-2', 'user_timestamp']),
                set(data.keys()))

    @inlineCallbacks
    def test_export_user_data_as_csv(self):
        poll = yield self.mkpoll_for_export()
        csv_data = (yield self.poll_manager.export_user_data_as_csv(poll))
        self.assertEqual(csv_data.split('\r\n')[0],
            'user_id,user_timestamp,question-0,question-1,question-2')
        self.assertTrue(csv_data.split('\r\n')[1].startswith(
            'user-1,%s' % (datetime.now().date(),)))

    @inlineCallbacks
    def test_export_user_data_as_csv_with_old_questions(self):
        poll = yield self.mkpoll_for_export()
        # remove some questions from the poll
        del poll.questions[1:]
        csv_data = yield self.poll_manager.export_user_data_as_csv(
            poll, include_old_questions=True)
        self.assertEqual(csv_data.split('\r\n')[0],
            'user_id,user_timestamp,question-0,question-1,question-2')
        self.assertTrue(csv_data.split('\r\n')[1].startswith(
            'user-1,%s' % (datetime.now().date(),)))


class MultiLevelPollManagerTestCase(PersistenceMixin, TestCase):

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
        yield self._persist_setUp()
        self.redis = yield self.get_redis_manager()
        self.poll_manager = PollManager(self.redis)
        self.poll_id = 'poll-id'
        self.poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions,
        })
        self.participant = yield self.poll_manager.get_participant(
            self.poll_id, 'user_id')

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()
        yield self._persist_tearDown()

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
    def test_case_insensitivity_on_checks(self):
        poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.default_questions,
            'case_sensitive': False,
        })
        participant = yield self.poll_manager.get_participant(self.poll_id,
            'user_id')
        # the check is for 'green' (lower case), however since the poll
        # is case-insensitive this should still pass
        participant.set_label('favorite colour', 'GREEN')
        participant.set_last_question_index(0)
        next_question_copy = 'What sort of green? Dark or Light?'
        next_question = poll.get_next_question(participant)
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
