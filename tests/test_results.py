from pprint import pprint
import csv

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import SkipTest

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vxpolls.results import ResultManager, CollectionException


class PollResultsTestCase(ApplicationTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(PollResultsTestCase, self).setUp()
        self.r_server = FakeRedis()
        self.r_prefix = 'test_results'
        self.manager = ResultManager(self.r_server, self.r_prefix)

    def mk_collection(self, collection_id):
        return self.manager.register_collection(collection_id)

    def test_register_collection(self):
        self.assertTrue(self.mk_collection('unique-id'))
        self.assertTrue(self.manager.register_question('unique-id',
            'question-id', ['answer']))
        self.assertTrue(self.manager.add_result('unique-id', 'user-id',
            'question-id', 'answer'))

    def test_unregistered_collection(self):
        self.assertRaises(CollectionException,
            self.manager.add_result,
            'unknown-collection-id', 'user-id', 'question', 'answer')

    def test_register_question(self):
        collection = self.mk_collection('unique-id')
        key = self.manager.register_question('unique-id',
            'what is your favorite colour?', ['red', 'green', 'blue'])

    def test_unregistered_question(self):
        self.assertRaises(CollectionException,
            self.manager.register_question, 'unknown-id',
                'some question', ['red', 'green', 'blue'])

    def test_add_result(self):
        collection_id = 'unique-id'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']
        user_id = '27761234567'

        self.mk_collection(collection_id)
        self.manager.register_question(collection_id, question, possible_answers)
        self.manager.add_result(collection_id, user_id, question, 'red')
        self.assertEqual(
            self.manager.get_results_for_question(collection_id, question),
            {
                'red': 1,
                'green': 0,
                'blue': 0,
            }
        )

    def test_get_results(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        self.mk_collection(collection_id)
        self.manager.register_question(collection_id, question, possible_answers)
        self.manager.add_result(collection_id, user_id, question, 'blue')

        self.assertEqual(self.manager.get_results(collection_id), {
            question: {
                'red': 0,
                'green': 0,
                'blue': 1,
            }
        })

    def test_get_results_per_user(self):
        """
        A user can only have 1 result in the result set for a given
        question. If questions are repeatedly answered differently
        then the last one will always win.
        """
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        self.mk_collection(collection_id)
        self.manager.register_question(collection_id, question, possible_answers)
        self.manager.add_result(collection_id, user_id, question, 'red')
        self.manager.add_result(collection_id, user_id, question, 'green')
        self.manager.add_result(collection_id, user_id, question, 'blue')
        self.manager.add_result(collection_id, user_id, question, 'blue')
        self.manager.add_result(collection_id, user_id, question, 'blue')
        self.manager.add_result(collection_id, user_id, question, 'blue')

        self.assertEqual(self.manager.get_results(collection_id), {
            question: {
                'red': 0,
                'green': 0,
                'blue': 1,
            }
        })

    def test_get_results_per_different_users(self):
        """
        A user can only have 1 result in the result set for a given
        question. If questions are repeatedly answered differently
        then the last one will always win.
        """
        collection_id = 'unique-id'
        user_id1 = '27761234560'
        user_id2 = '27761234561'
        user_id3 = '27761234562'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']
        self.mk_collection(collection_id)
        self.manager.register_question(collection_id, question,
                                        possible_answers)
        for user_id in [user_id1, user_id2, user_id3]:
            for colour in possible_answers:
                self.manager.add_result(collection_id, user_id,
                    question, colour)

        self.assertEqual(self.manager.get_results(collection_id), {
            question: {
                'red': 0,
                'green': 0,
                'blue': 3,
            }
        })


    def test_context_manager_add_result(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            m.register_question(question, possible_answers)
            m.add_result(question, 'red')
            self.assertEqual(m.get_questions(), set([question]))
            self.assertEqual(m.get_answers(question), set(possible_answers))
            self.assertEqual(m.user_id, user_id)
            self.assertEqual(m.collection_id, collection_id)
            self.assertEqual(m.get_results(), {
                question: {
                    'red': 1,
                    'green': 0,
                    'blue': 0,
                }
            })
            self.assertEqual(m.get_results_for_question(question), {
                'red': 1,
                'green': 0,
                'blue': 0,
            })
            self.assertEqual(m.get_user(), {
                question: 'red',
            })

        self.assertEqual(
            self.manager.get_results_for_question(collection_id, question), {
                'red': 1,
                'green': 0,
                'blue': 0,
            })

    def test_get_users(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            m.register_question(question, possible_answers)
            m.add_result(question, 'red')

        users = list(self.manager.get_users(collection_id))
        self.assertEqual(users, [(user_id, {
            question: 'red',
        })])

    def test_get_users_as_csv(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            m.register_question(question, possible_answers)
            m.add_result(question, 'red')

        sio = self.manager.get_users_as_csv(collection_id)
        self.assertEqual(sio.getvalue(), "\r\n".join([
            "user_id,%s" % (question,),
            "%s,%s" % (user_id, 'red'),
            ""
        ]))

    def test_get_results_as_csv(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            m.register_question(question, possible_answers)
            m.add_result(question, 'red')

        sio = self.manager.get_results_as_csv(collection_id)
        self.assertEqual(sio.getvalue(), "\r\n".join([
            ",blue,green,red",
            "%s,%s,%s,%s" % (question, 0, 0, 1),
            ""
        ]))
