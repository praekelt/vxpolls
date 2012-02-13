import json
import urllib
import csv

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from vxpolls.manager import PollManager
from vxpolls.results import ResultManager
from vxpolls.dashboard import PollDashboardServer

from vumi.tests.utils import FakeRedis

class PollDashboardTestCase(TestCase):

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
        self.r_server = FakeRedis()
        self.poll_manager = PollManager(self.r_server, self.questions)
        self.results_manager = ResultManager(self.r_server)
        # Let the results manager know what collections it should be
        # aware of.
        self.results_manager.register_collection(self.poll_id)
        # let the results manager know of the questions available and
        # what it is tracking results for.
        for entry in self.questions:
            self.results_manager.register_question(self.poll_id, entry['copy'],
                [resp.lower() for resp in entry['valid_responses']])

        self.service = PollDashboardServer(self.poll_manager,
                                            self.results_manager, 0, '')
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.poll_manager.stop()
        yield self.service.stopService()

    @inlineCallbacks
    def get_route_json(self, route):
        data = yield getPage(self.url + route, timeout=1)
        returnValue(json.loads(data))

    @inlineCallbacks
    def get_route_csv(self, route):
        data = yield getPage(self.url + route, timeout=1)
        returnValue(csv.reader(data))

    def submit_answers(self, *answers, **kwargs):
        for answer in answers:
            participant = self.poll_manager.get_participant(kwargs.get('user_id', 'user_id'))
            question = self.poll_manager.get_next_question(participant)
            self.poll_manager.set_last_question(participant, question)
            error_message = self.poll_manager.submit_answer(participant, answer)
            if error_message:
                raise ValueError(error_message)
            self.poll_manager.save_participant(participant)

    @inlineCallbacks
    def test_question_output(self):
        data = yield self.get_route_json("results?%s" % urllib.urlencode({
            'collection_id': self.poll_id,
            'question': 'What is your favorite colour?'
        }))
        self.assertEqual(data, {
            "type": "standard",
            "percentage": "hide",
            "item": [
                { "label": "blue".title(), "value": 0},
                { "label": "green".title(), "value": 0},
                { "label": "red".title(), "value": 0},
            ]
        })

    @inlineCallbacks
    def test_active_output(self):
        starting_output = [
            {'colour': '#4F993C', 'label': 'Active', 'value': 0},
            {'colour': '#992E2D', 'label': 'Inactive', 'value': 0},
        ]
        data = yield self.get_route_json('active')
        self.assertEqual(data, {
            "item": starting_output,
        })

        self.submit_answers('red', 'orange', 'apple')

        updated_output = starting_output[:]
        updated_output[0] = {
            'colour': '#4F993C',
            'label': 'Active',
            'value': 1,
        }

        data = yield self.get_route_json('active')
        self.assertEqual(data, {
            "item": updated_output,
        })

    @inlineCallbacks
    def test_results_csv(self):
        data = yield self.get_route_csv('results.csv?%s' % (urllib.urlencode({
            'collection_id': self.poll_id,
        }),))

    @inlineCallbacks
    def test_users_csv(self):
        data = yield self.get_route_csv('users.csv?%s' % (urllib.urlencode({
            'collection_id': self.poll_id,
        }),))
