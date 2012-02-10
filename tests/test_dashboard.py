import json
import urllib
import csv

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from tests.test_polls import BasePollTestCase
from vxpolls.dashboard import PollDashboardServer


class PollResultsResourceTestCase(BasePollTestCase):

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
        yield super(PollResultsResourceTestCase, self).setUp()
        self.app = yield self.create_poll(questions=self.questions)
        self.service = PollDashboardServer(self.app.poll_manager,
                                            self.app.results_manager, 0, '')
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield super(PollResultsResourceTestCase, self).tearDown()
        yield self.service.stopService()

    @inlineCallbacks
    def get_route_json(self, route):
        data = yield getPage(self.url + route, timeout=1)
        returnValue(json.loads(data))

    @inlineCallbacks
    def get_route_csv(self, route):
        data = yield getPage(self.url + route, timeout=1)
        returnValue(csv.reader(data))

    @inlineCallbacks
    def test_question_output(self):
        data = yield self.get_route_json("results?%s" % urllib.urlencode({
            'collection_id': self.app.poll_id,
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

        yield self.submit_messages("18", "red", "orange", "apple")
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
    def test_completed_output(self):
        starting_output = [
            {'colour': '#4F993C', 'label': 'Complete', 'value': 0},
            {'colour': '#992E2D', 'label': 'Incomplete', 'value': 0},
        ]
        data = yield self.get_route_json('completed?%s' % urllib.urlencode({
            'collection_id': self.app.poll_id,
        }))
        self.assertEqual(data, {
            "item": starting_output,
        })

        yield self.submit_messages("18", "red", "orange", "apple")
        updated_output = starting_output[:]
        updated_output[0] = {
            'colour': '#4F993C',
            'label': 'Complete',
            'value': 1,
        }

        data = yield self.get_route_json('completed?%s' % urllib.urlencode({
            'collection_id': self.app.poll_id,
        }))
        self.assertEqual(data, {
            "item": updated_output,
        })

    @inlineCallbacks
    def test_results_csv(self):
        data = yield self.get_route_csv('results.csv?%s' % (urllib.urlencode({
            'collection_id': self.app.poll_id,
        }),))

    @inlineCallbacks
    def test_users_csv(self):
        data = yield self.get_route_csv('users.csv?%s' % (urllib.urlencode({
            'collection_id': self.app.poll_id,
        }),))
