import yaml

from django.test.client import Client
from django.test import TestCase
from django.core.urlresolvers import reverse
from vumi.tests.utils import FakeRedis
from vxpolls.manager import PollManager
from vxpolls.content import forms
from vxpolls.content import views as content_views


class VxpollFormTestCase(TestCase):

    maxDiff = None
    config_data = """
    transport_name: vxpolls_transport
    batch_size: 2
    poll_id: 'poll-1'
    questions:
      - copy: 'What is your favorite color? 1. Red 2. Yellow 3. Blue'
        label: favorite color
        valid_responses:
          - '1'
          - '2'
          - '3'
      - copy: 'What shade of red? 1. Dark or 2. Light'
        label: what shade
        valid_responses:
          - '1'
          - '2'
        checks:
          equal:
              favorite color: '1'
      - copy: 'What is your favorite fruit? 1. Apples 2. Oranges 3. Bananas'
        label: favorite fruit
        valid_responses:
          - '1'
          - '2'
          - '3'
      - copy: 'What is your favorite editor? 1. Vim 2. Emacs 3. Other'
        label: favorite editor
        valid_responses:
          - '1'
          - '2'
          - '3'
    """

    def setUp(self):
        self.config = yaml.load(self.config_data)
        self.r_server = FakeRedis()
        self.poll_manager = PollManager(self.r_server)
        self.poll_id = self.config['poll_id']
        self.poll = self.poll_manager.register(self.poll_id, self.config)
        self.client = Client()
        # Monkey patch the views redis attribute to point to our Fake redis
        content_views.redis = self.r_server

    def test_form_creation(self):
        form = forms.make_form(data=self.config.copy(), initial=self.config.copy())
        self.assertEqual(form.errors, {})
        self.assertTrue(form.is_valid())
        export = form.export()
        self.assertEqual(export['transport_name'], self.config['transport_name'])
        self.assertEqual(export['batch_size'], self.config['batch_size'])
        self.assertEqual(export['poll_id'], self.config['poll_id'])
        for index, question in enumerate(export['questions']):
            config_question = self.config['questions'][index]
            self.assertEqual(config_question['copy'], question['copy'])
            self.assertEqual(config_question.get('checks', {}),
                                question.get('checks', {}))
            self.assertEqual(config_question.get('label'),
                                question.get('label'))
            self.assertEqual(config_question['valid_responses'],
                                question['valid_responses'])

    def test_form_posting(self):
        response = self.client.post(reverse('content:home'), {
            'question__0__copy': 'What is your favorite music?',
            'question__0__label': 'favorite music',
            'question__0__valid_responses': 'rock, jazz, techno',
            'question__0__checks_0': 'a',
            'question__0__checks_1': 'b',
        })
        poll = self.poll_manager.get(self.poll_id)
        self.assertEqual(response.status_code, 200)
        # print poll.questions[0]