# -*- test-case-name: tests.test_results -*-
import csv

from functools import partial
from StringIO import StringIO

from twisted.internet.defer import returnValue

from vumi.persist.redis_base import Manager


class ResultManagerException(Exception):
    pass


class CollectionException(ResultManagerException):
    pass


class ResultManager(object):

    def __init__(self, r_server, r_prefix='results'):
        # create a manager instances so the @calls_manager works
        self.r_server = self.manager = r_server
        self.r_prefix = r_prefix
        self.collections_prefix = 'collections'
        self.questions_prefix = 'questions'
        self.answers_prefix = 'answers'
        self.results_prefix = 'results'
        self.users_prefix = 'users'

    def defaults(self, collection_id, user_id):
        return ContextResultManager(collection_id, user_id, self)

    def r_key(self, *args):
        return ':'.join([self.r_prefix] + list(args))

    def get_collection_key(self, collection_id):
        return self.r_key(self.collections_prefix, collection_id)

    def get_results_key(self, collection_id, key):
        return self.r_key(self.collections_prefix, collection_id,
            self.results_prefix, key)

    def get_questions_key(self, collection_id):
        return self.r_key(self.collections_prefix, collection_id,
            self.questions_prefix)

    def get_answers_key(self, collection_id, question):
        return self.r_key(self.collections_prefix, collection_id,
            self.answers_prefix, question)

    def get_users_key(self, collection_id):
        return self.r_key(self.collections_prefix, collection_id,
            self.users_prefix)

    def get_user_answers_key(self, collection_id, user_id):
        return self.r_key(self.collections_prefix, collection_id,
            self.users_prefix, self.results_prefix, user_id)

    def register_collection(self, collection_id):
        collection_key = self.r_key(self.collections_prefix)
        return self.r_server.sadd(collection_key, collection_id)

    def get_collections(self):
        collection_key = self.r_key(self.collections_prefix)
        return self.r_server.smembers(collection_key)

    @Manager.calls_manager
    def get_questions(self, collection_id):
        questions_key = self.get_questions_key(collection_id)
        questions = yield self.r_server.smembers(questions_key)
        returnValue(set([q.decode('utf-8') for q in questions]))

    @Manager.calls_manager
    def get_answers(self, collection_id, question):
        answers_key = self.get_answers_key(collection_id, question)
        answers = yield self.r_server.smembers(answers_key)
        returnValue(set([q.decode('utf-8') for q in answers]))

    @Manager.calls_manager
    def register_question(self, collection_id, question,
        possible_answers=None):
        """
        :param collection_id:       the unique id of the collection / survey
        :param question:            the unique id of the question asked
        :param possible_answers:    the list of possible answers this question
                                    can expect.
        """
        collection_ids = yield self.get_collections()
        if collection_id not in collection_ids:
            raise CollectionException('%s is an unknown collection' % (
                                        collection_id,))
        questions_key = self.get_questions_key(collection_id)
        yield self.r_server.sadd(questions_key, question)
        answers_key = self.get_answers_key(collection_id, question)
        if possible_answers:
            for answer in possible_answers:
                if not (yield self.r_server.sismember(answers_key, answer)):
                    yield self.r_server.sadd(answers_key, answer)
        answers = yield self.get_answers(collection_id, question)
        returnValue(answers)

    @Manager.calls_manager
    def add_result(self, collection_id, user_id, question, answer):
        """
        :param collection_id:   the unique id of the collection we're tracking
                                results for. In this case it'd be a unique
                                id to identify a poll.
        :param user_id:         the unique id of the user submitting the
                                result.
        :param question:        the question we're tracking answers for.
        :param answer:          the answer we're counting votes for
        """
        collection_ids = yield self.get_collections()
        if collection_id not in collection_ids:
            raise CollectionException('%s is an unknown collection.' % (
                                        collection_id,))

        questions = yield self.get_questions(collection_id)
        if question not in questions:
            raise ResultManagerException(
                '%s is an unknown question.' % (question.encode('utf-8'),))

        users_key = self.get_users_key(collection_id)
        yield self.r_server.sadd(users_key, user_id)
        users_answers_key = self.get_user_answers_key(collection_id, user_id)
        results_key = self.get_results_key(collection_id, question)
        previous_answer = yield self.r_server.hget(users_answers_key, question)
        if previous_answer:
            # we've already seen an answer for this question before
            # so we need to shuffle things around instead of just
            # incrementing.
            yield self.r_server.hincrby(results_key, answer, 1)
            yield self.r_server.hincrby(results_key, previous_answer, -1)
        elif previous_answer != answer:
            # we've not seen this entry for this user yet so just
            # simply increment a counter
            yield self.r_server.hincrby(results_key, answer, 1)

        yield self.r_server.hset(users_answers_key, question, answer)
        returnValue(results_key)

    @Manager.calls_manager
    def get_results(self, collection_id):
        questions = yield self.get_questions(collection_id)
        results = []
        for question in questions:
            result = yield self.get_results_for_question(collection_id,
                question)
            results.append((question, result))
        returnValue(dict(results))

    @Manager.calls_manager
    def get_results_for_question(self, collection_id, question):
        results_key = self.get_results_key(collection_id, question)
        answers = yield self.get_answers(collection_id, question)
        # If we've been given a list of possible answers, return the
        # full list of possible answers and automatically set 0
        # as the value for the answers that haven't been given
        # any votes
        if answers:
            results = []
            for answer in answers:
                if (yield self.r_server.hexists(results_key, answer)):
                    result = yield self.r_server.hget(results_key, answer)
                else:
                    result = 0
                results.append((answer, int(result)))
            returnValue(dict(results))
        else:
            results = yield self.r_server.hgetall(results_key)
            answers = []
            for answer, value in results.items():
                answers.append((answer, int(value)))
            returnValue(dict(answers))

    @Manager.calls_manager
    def get_users(self, collection_id, questions=None):
        users_key = self.get_users_key(collection_id)
        user_ids = yield self.r_server.smembers(users_key)
        users = []
        for user_id in user_ids:
            user = yield self.get_user(collection_id, user_id, questions)
            users.append((user_id, user))
        returnValue(users)

    @Manager.calls_manager
    def get_user(self, collection_id, user_id, questions=None):
        answers_key = self.get_user_answers_key(collection_id, user_id)
        questions = questions or (yield self.get_questions(collection_id))
        user_results = []
        for question in questions:
            answer = yield self.r_server.hget(answers_key, question)
            user_results.append((question, answer))
        returnValue(dict(user_results))

    @Manager.calls_manager
    def get_users_as_csv(self, collection_id):
        sio = StringIO()
        fieldnames = ['user_id']
        questions = yield self.get_questions(collection_id)
        fieldnames.extend(questions)
        fieldnames = [fn.encode('utf8') for fn in fieldnames]
        headers = dict((n, n) for n in fieldnames)
        writer = csv.DictWriter(sio, fieldnames=fieldnames)
        writer.writerow(headers)
        users = yield self.get_users(collection_id)
        for user_id, user_data in users:
            data = {
                'user_id': user_id,
            }
            data.update(user_data)
            writer.writerow(data)
        returnValue(sio)

    @Manager.calls_manager
    def get_results_as_csv(self, collection_id):
        sio = StringIO()
        writer = csv.writer(sio)
        results = yield self.get_results(collection_id)
        for question, results in results.items():
            writer.writerow([''] + results.keys())
            writer.writerow([question.encode('utf8')] + results.values())
        returnValue(sio)


class ContextResultManager(object):
    def __init__(self, collection_id, user_id, result_manager):
        self.collection_id = collection_id
        self.user_id = user_id
        result_manager.register_collection(self.collection_id)

        # wrap all calls that only expect collection_id
        wrap_collection_ids = [
            'get_questions',
            'get_answers',
            'register_question',
            'get_results',
            'get_results_for_question',
            'get_users',
        ]
        for func_name in wrap_collection_ids:
            wrapped = partial(getattr(result_manager, func_name),
                                self.collection_id)
            setattr(self, func_name, wrapped)

        # wrap all calls that expect collection_id and user_id
        wrap_collection_and_user_ids = [
            'add_result',
            'get_user',
        ]
        for func_name in wrap_collection_and_user_ids:
            wrapped = partial(getattr(result_manager, func_name),
                                self.collection_id, self.user_id)
            setattr(self, func_name, wrapped)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
