# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.utils import ApplicationTestCase

from vxpolls.results import (
    ResultManager, ResultManagerException, CollectionException)


class PollResultsTestCase(ApplicationTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(PollResultsTestCase, self).setUp()
        self.redis = yield self.get_redis_manager()
        self.r_prefix = 'test_results'
        self.manager = ResultManager(self.redis, self.r_prefix)

    def mk_collection(self, collection_id):
        return self.manager.register_collection(collection_id)

    def assert_collections(self, *expected):
        d = self.manager.get_collections()
        return d.addCallback(self.assertEqual, set(expected))

    def assert_questions(self, collection_id, *expected):
        d = self.manager.get_questions(collection_id)
        return d.addCallback(self.assertEqual, set(expected))

    @inlineCallbacks
    def test_register_collection(self):
        yield self.assert_collections()
        yield self.mk_collection('unique-id')
        yield self.assert_collections('unique-id')

    @inlineCallbacks
    def test_register_question(self):
        yield self.mk_collection('cid')
        yield self.assert_questions('cid')
        answers = yield self.manager.register_question(
            'cid', 'what is your favorite colour?', ['red', 'green', 'blue'])
        yield self.assert_questions('cid', 'what is your favorite colour?')
        self.assertEqual(answers, set(['red', 'green', 'blue']))

    def test_unregistered_collection(self):
        return self.assertFailure(
            self.manager.register_question('cid', 'some question',
                                           ['red', 'green', 'blue']),
            CollectionException)

    @inlineCallbacks
    def test_unregistered_question(self):
        yield self.assertFailure(
            self.manager.add_result('cid', 'uid', 'question', 'answer'),
            CollectionException)
        yield self.mk_collection('cid')
        yield self.assertFailure(
            self.manager.add_result('cid', 'uid', 'question', 'answer'),
            ResultManagerException)

    @inlineCallbacks
    def test_add_result(self):
        collection_id = 'unique-id'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']
        user_id = '27761234567'

        yield self.mk_collection(collection_id)
        yield self.manager.register_question(collection_id, question, possible_answers)
        yield self.manager.add_result(collection_id, user_id, question, 'red')
        result = yield self.manager.get_results_for_question(collection_id,
            question)
        self.assertEqual(result, {
                'red': 1,
                'green': 0,
                'blue': 0,
            }
        )

    @inlineCallbacks
    def test_get_results(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        yield self.mk_collection(collection_id)
        yield self.manager.register_question(collection_id, question,
            possible_answers)
        yield self.manager.add_result(collection_id, user_id, question, 'blue')

        results = yield self.manager.get_results(collection_id)
        self.assertEqual(results, {
            question: {
                'red': 0,
                'green': 0,
                'blue': 1,
            }
        })

    @inlineCallbacks
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

        yield self.mk_collection(collection_id)
        yield self.manager.register_question(collection_id, question,
            possible_answers)
        yield self.manager.add_result(collection_id, user_id, question, 'red')
        yield self.manager.add_result(collection_id, user_id, question, 'green')
        yield self.manager.add_result(collection_id, user_id, question, 'blue')
        yield self.manager.add_result(collection_id, user_id, question, 'blue')
        yield self.manager.add_result(collection_id, user_id, question, 'blue')
        yield self.manager.add_result(collection_id, user_id, question, 'blue')

        results = yield self.manager.get_results(collection_id)
        self.assertEqual(results, {
            question: {
                'red': 0,
                'green': 0,
                'blue': 1,
            }
        })

    @inlineCallbacks
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
        yield self.mk_collection(collection_id)
        yield self.manager.register_question(collection_id, question,
                                        possible_answers)
        for user_id in [user_id1, user_id2, user_id3]:
            for colour in possible_answers:
                yield self.manager.add_result(collection_id, user_id,
                    question, colour)

        results = yield self.manager.get_results(collection_id)
        self.assertEqual(results, {
            question: {
                'red': 0,
                'green': 0,
                'blue': 3,
            }
        })


    @inlineCallbacks
    def test_context_manager_add_result(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            yield m.register_question(question, possible_answers)
            yield m.add_result(question, 'red')
            self.assertEqual((yield m.get_questions()), set([question]))
            self.assertEqual((yield m.get_answers(question)),
                set(possible_answers))
            self.assertEqual(m.user_id, user_id)
            self.assertEqual(m.collection_id, collection_id)
            self.assertEqual((yield m.get_results()), {
                question: {
                    'red': 1,
                    'green': 0,
                    'blue': 0,
                }
            })
            self.assertEqual((yield m.get_results_for_question(question)), {
                'red': 1,
                'green': 0,
                'blue': 0,
            })
            self.assertEqual((yield m.get_user()), {
                question: 'red',
            })

        results = yield self.manager.get_results_for_question(collection_id,
            question)
        self.assertEqual(
            results, {
                'red': 1,
                'green': 0,
                'blue': 0,
            })

    @inlineCallbacks
    def test_get_users(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            yield m.register_question(question, possible_answers)
            yield m.add_result(question, 'red')

        users = (yield self.manager.get_users(collection_id))
        self.assertEqual(users, [(user_id, {
            question: 'red',
        })])

    @inlineCallbacks
    def test_get_users_as_csv(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            yield m.register_question(question, possible_answers)
            yield m.add_result(question, 'red')

        sio = yield self.manager.get_users_as_csv(collection_id)
        self.assertEqual(sio.getvalue(), "\r\n".join([
            "user_id,%s" % (question,),
            "%s,%s" % (user_id, 'red'),
            ""
        ]))

    @inlineCallbacks
    def test_get_users_limit_question_results(self):
        collection_id = 'unique-id'
        user_ids = ['27761234567', '27761234568']
        questions = ['one', 'two', 'three']

        for user_id in user_ids:
            with self.manager.defaults(collection_id, user_id) as m:
                for question in questions:
                    yield m.register_question(question)
                    yield m.add_result(question, 'answer %s' % (question,))

        users = yield self.manager.get_users(collection_id)
        self.assertEqual(sorted(users, key=lambda t: t[0]), [
            ('27761234567', {
                'one': 'answer one',
                'two': 'answer two',
                'three': 'answer three',
            }),
            ('27761234568', {
                'one': 'answer one',
                'two': 'answer two',
                'three': 'answer three',
            }),
        ])

        limited_users = yield self.manager.get_users(collection_id,
                                            questions=['one', 'two'])
        self.assertEqual(sorted(limited_users, key=lambda t: t[0]), [
            ('27761234567', {
                'one': 'answer one',
                'two': 'answer two',
            }),
            ('27761234568', {
                'one': 'answer one',
                'two': 'answer two',
            }),
        ])

    @inlineCallbacks
    def test_get_results_as_csv(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        question = 'what is your favorite colour?'
        possible_answers = ['red', 'green', 'blue']

        with self.manager.defaults(collection_id, user_id) as m:
            yield m.register_question(question, possible_answers)
            yield m.add_result(question, 'red')

        sio = yield self.manager.get_results_as_csv(collection_id)
        self.assertEqual(sio.getvalue(), "\r\n".join([
            ",blue,green,red",
            "%s,%s,%s,%s" % (question, 0, 0, 1),
            ""
        ]))

    @inlineCallbacks
    def test_handling_of_weird_characters(self):
        # This is data received in an actual campaign that tripped stuff up.
        collection_id = 'unique-id'
        user_id = '27761234567'

        data = {'dob': 'Chelsea  will  win  2\xc3\x82\xc2\xa71  '
                        'against  Athletico  Madrid.By  Annor 1.',
                }
        with self.manager.defaults(collection_id, user_id) as m:
            for question, answer in data.items():
                yield m.register_question(question)
                yield m.add_result(question, answer)

        unicode_str = unicode(data['dob'], 'utf-8')
        utf8_str = unicode_str.encode('utf-8')

        sio = yield self.manager.get_users_as_csv(collection_id)
        self.assertEqual(sio.getvalue(), '\r\n'.join([
            "user_id,dob",
            "27761234567,%s" % (utf8_str,),
            ""
            ]))

    @inlineCallbacks
    def test_unicode_questions(self):
        collection_id = 'unique-id'
        user_id = '27761234567'
        # NOTE: copy taken from a failing production scenario, please not the
        #       "curly quote" in `We'd`.
        question = u'Hi, welcome to the Star Menu test system. We’d ' \
                   u'like you to answer a few questions for us. Please ' \
                   u'tell us your first name.'

        with self.manager.defaults(collection_id, user_id) as m:
            yield m.register_question(question)

        # This would've blown up before
        yield m.add_result(question, 'foo')
        [stored_question] = yield m.get_questions()
        self.assertEqual(stored_question, question)
