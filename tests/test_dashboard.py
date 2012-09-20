import json
import urllib
import csv

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from vumi.tests.utils import PersistenceMixin

from vxpolls.manager import PollManager
from vxpolls.dashboard import PollDashboardServer


class PollDashboardTestCase(PersistenceMixin, TestCase):

    poll_id = 'poll-id'
    questions = [{
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
        self.poll = yield self.poll_manager.register(self.poll_id, {
            'questions': self.questions,
        })
        self.results_manager = yield self.poll.results_manager
        # Let the results manager know what collections it should be
        # aware of.
        yield self.results_manager.register_collection(self.poll_id)
        # let the results manager know of the questions available and
        # what it is tracking results for.
        for entry in self.questions:
            yield self.results_manager.register_question(
                self.poll_id, entry['copy'],
                [resp.lower() for resp in entry['valid_responses']])

        self.service = PollDashboardServer(self.poll_manager,
                                    self.results_manager, {
                                        'port': 0,
                                        'path': '',
                                        'collection_id': self.poll_id,
                                        'question': self.questions[0]['copy']
                                    })
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()
        yield self.service.stopService()
        yield self._persist_tearDown()

    @inlineCallbacks
    def get_route_json(self, route, **kwargs):
        data = yield getPage(self.url + route + '?' + urllib.urlencode(kwargs),
                                timeout=1)
        returnValue(json.loads(data))

    @inlineCallbacks
    def get_route_csv(self, route, **kwargs):
        data = yield getPage(self.url + route + '?' + urllib.urlencode(kwargs),
                                timeout=1)
        returnValue(csv.reader(data))

    @inlineCallbacks
    def submit_answers(self, *answers, **kwargs):
        for answer in answers:
            participant = yield self.poll_manager.get_participant(self.poll_id,
                            kwargs.get('user_id', 'user_id'))
            participant.set_poll_id(self.poll_id)
            question = self.poll.get_next_question(participant)
            self.poll.set_last_question(participant, question)
            error_message = yield self.poll.submit_answer(participant, answer)
            if error_message:
                raise ValueError(error_message)
            yield self.poll_manager.save_participant(self.poll_id, participant)

    @inlineCallbacks
    def test_question_output(self):
        data = yield self.get_route_json("results",
            collection_id=self.poll_id,
            question='What is your favorite colour?',
        )
        self.assertEqual(data, {
            "type": "standard",
            "percentage": "hide",
            "item": [
                {"label": "blue".title(), "value": 0},
                {"label": "green".title(), "value": 0},
                {"label": "red".title(), "value": 0},
            ]
        })

    @inlineCallbacks
    def test_active_output(self):
        starting_output = [
            {'colour': '#4F993C', 'label': 'Active', 'value': 0},
            {'colour': '#992E2D', 'label': 'Inactive', 'value': 0},
        ]
        data = yield self.get_route_json('active', poll_id=self.poll_id)
        self.assertEqual(data, {
            "item": starting_output,
        })

        yield self.submit_answers('red', 'orange', 'apple')

        updated_output = starting_output[:]
        updated_output[0] = {
            'colour': '#4F993C',
            'label': 'Active',
            'value': 1,
        }

        data = yield self.get_route_json('active', poll_id=self.poll_id)
        self.assertEqual(data, {
            "item": updated_output,
        })

    @inlineCallbacks
    def test_results_csv(self):
        yield self.get_route_csv('results.csv?%s' % (urllib.urlencode({
            'collection_id': self.poll_id,
        }),))

    @inlineCallbacks
    def test_users_csv(self):
        yield self.get_route_csv('users.csv?%s' % (urllib.urlencode({
            'collection_id': self.poll_id,
        }),))
