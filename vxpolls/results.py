# -*- test-case-name: tests.test_results -*-
import csv
from functools import partial
from StringIO import StringIO

class ResultManagerException(Exception): pass
class CollectionException(ResultManagerException): pass


class ResultManager(object):

    def __init__(self, r_server, r_prefix='results'):
        self.r_server = r_server
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
        self.r_server.sadd(collection_key, collection_id)
        return collection_key

    def get_collections(self):
        collection_key = self.r_key(self.collections_prefix)
        return self.r_server.smembers(collection_key)

    def get_questions(self, collection_id):
        questions_key = self.get_questions_key(collection_id)
        return self.r_server.smembers(questions_key)

    def get_answers(self, collection_id, question):
        answers_key = self.get_answers_key(collection_id, question)
        return self.r_server.smembers(answers_key)

    def register_question(self, collection_id, question,
        possible_answers=None):
        """
        :param collection_id:       the unique id of the collection / survey
        :param question:            the unique id of the question asked
        :param possible_answers:    the list of possible answers this question
                                    can expect.
        """
        if collection_id not in self.get_collections():
            raise CollectionException('%s is an unknown collection' % (
                                        collection_id,))
        questions_key = self.get_questions_key(collection_id)
        self.r_server.sadd(questions_key, question)
        answers_key = self.get_answers_key(collection_id, question)
        if possible_answers:
            self.r_server.sadd(answers_key, *possible_answers)
        return self.get_answers(collection_id, question)

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
        if collection_id not in self.get_collections():
            raise CollectionException('%s is an unknown collection.' % (
                                        collection_id,))

        if question not in self.get_questions(collection_id):
            raise ResultManagerException('%s is an unknown question.' % (
                                question,))

        users_key = self.get_users_key(collection_id)
        self.r_server.sadd(users_key, user_id)
        users_answers_key = self.get_user_answers_key(collection_id, user_id)
        results_key = self.get_results_key(collection_id, question)
        previous_answer = self.r_server.hget(users_answers_key, question)
        if previous_answer:
            # we've already seen an answer for this question before
            # so we need to shuffle things around instead of just
            # incrementing.
            self.r_server.hincrby(results_key, answer, 1)
            self.r_server.hincrby(results_key, previous_answer, -1)
        elif previous_answer != answer:
            # we've not seen this entry for this user yet so just
            # simply increment a counter
            self.r_server.hincrby(results_key, answer, 1)

        self.r_server.hset(users_answers_key, question, answer)
        return results_key

    def get_results(self, collection_id):
        return dict([(
            question,
            self.get_results_for_question(collection_id, question)
        ) for question in self.get_questions(collection_id)])

    def get_results_for_question(self, collection_id, question):
        results_key = self.get_results_key(collection_id, question)
        answers = self.get_answers(collection_id, question)
        # If we've been given a list of possible answers, return the
        # full list of possible answers and automatically set 0
        # as the value for the answers that haven't been given
        # any votes
        if answers:
            return dict([
                (
                    answer,
                    int(self.r_server.hget(results_key, answer) or 0)
                ) for answer in answers])
        else:
            return dict([(
                answer,
                int(value)
            ) for answer, value in self.r_server.hgetall(results_key).items()])

    def get_users(self, collection_id):
        users_key = self.get_users_key(collection_id)
        for user_id in self.r_server.smembers(users_key):
            yield user_id, self.get_user(collection_id, user_id)

    def get_user(self, collection_id, user_id):
        answers_key = self.get_user_answers_key(collection_id, user_id)
        return dict([(
            question,
            self.r_server.hget(answers_key, question)
        ) for question in self.get_questions(collection_id)])

    def encode_as_utf8(self, dictionary):
        return dict((k.encode('utf8'), (v or '').encode('utf8'))
                        for k, v in dictionary.items())

    def get_users_as_csv(self, collection_id):
        sio = StringIO()
        fieldnames = ['user_id']
        fieldnames.extend(self.get_questions(collection_id))
        fieldnames = [fn.encode('utf8') for fn in fieldnames]
        headers = self.encode_as_utf8(dict((n, n) for n in fieldnames))
        writer = csv.DictWriter(sio, fieldnames=fieldnames)
        writer.writerow(headers)
        for user_id, user_data in self.get_users(collection_id):
            data = {
                'user_id': user_id,
            }
            data.update(user_data)
            writer.writerow(self.encode_as_utf8(data))
        return sio

    def get_results_as_csv(self, collection_id):
        sio = StringIO()
        writer = csv.writer(sio)
        for question, results in self.get_results(collection_id).items():
            writer.writerow([''] + results.keys())
            writer.writerow([question.encode('utf8')] + results.values())
        return sio


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

