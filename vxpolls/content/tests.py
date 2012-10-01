import yaml

from django.conf import settings
from django.test.client import Client
from django.test import TestCase
from django.core.urlresolvers import reverse

from vumi.tests.utils import PersistenceMixin

from vxpolls.manager import PollManager
from vxpolls.content import forms
from vxpolls.content import views as content_views


class VxpollFormTestCase(PersistenceMixin, TestCase):
    sync_persistence = True

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
        self._persist_setUp()
        self.config = yaml.load(self.config_data)
        self.redis = self.get_redis_manager()
        self.poll_manager = PollManager(self.redis, settings.VXPOLLS_PREFIX)
        self.poll_id = self.config['poll_id']
        self.poll = self.poll_manager.register(self.poll_id, self.config)
        self.client = Client()
        # Monkey patch the views redis attribute to point to our Fake redis
        content_views.redis = self.redis

    def tearDown(self):
        super(TestCase, self).tearDown()
        self._persist_tearDown()

    def test_form_creation(self):
        form = forms.make_form(data=self.config.copy(),
                                initial=self.config.copy())
        self.assertEqual(form.errors, {})
        self.assertTrue(form.is_valid())
        export = form.export()
        self.assertEqual(export['transport_name'],
                          self.config['transport_name'])
        self.assertEqual(export['batch_size'], self.config['batch_size'])
        self.assertEqual(export['poll_id'], self.config['poll_id'])

        def new_checks_style(config_question):
            check = config_question.get('checks') or {'equal': {'': ''}}
            equal = check['equal']
            return [['equal', equal.keys()[0], equal.values()[0]]]

        for index, question in enumerate(export['questions']):
            config_question = self.config['questions'][index]
            self.assertEqual(config_question['copy'], question['copy'])
            self.assertEqual(new_checks_style(config_question),
                                question.get('checks'))
            self.assertEqual(config_question.get('label'),
                                question.get('label'))
            self.assertEqual(config_question['valid_responses'],
                                question['valid_responses'])

    def test_form_set(self):
        response = self.client.post(reverse('content:formset', kwargs={
            'poll_id': self.poll_id,
            }), {
            'question-TOTAL_FORMS': 1,
            'question-INITIAL_FORMS': 0,
            'question-MAX_NUM_FORMS': '',
            'question-0-copy': 'What is your favorite music?',
            'question-0-label': 'favorite music',
            'question-0-valid_responses': 'rock, jazz, techno',
            'completed_response-TOTAL_FORMS': 0,
            'completed_response-INITIAL_FORMS': 0,
            'completed_response-MAX_NUM_FORMS': '',
        })
        uid = self.poll_manager.get_latest_uid(self.poll_id)
        poll = self.poll_manager.get(self.poll_id, uid)
        self.assertRedirects(response, reverse('content:formset', kwargs={
            'poll_id': self.poll_id,
            }))
        self.assertEqual(len(poll.questions), 1)
        # test that the new version is actually being served
        participant = self.poll_manager.get_participant(self.poll_id,
                'somemsisdn')
        question = poll.get_next_question(participant)
        self.assertEqual(question.copy, 'What is your favorite music?')

    def test_form_set_checks(self):
        response = self.client.post(reverse('content:formset', kwargs={
            'poll_id': self.poll_id,
            }), {
            'question-TOTAL_FORMS': 3,
            'question-INITIAL_FORMS': 0,
            'question-MAX_NUM_FORMS': '',
            'question-0-copy': 'What is your favorite music?',
            'question-0-label': 'favorite music',
            'question-0-valid_responses': 'rock, jazz, techno',
            'question-1-copy': 'What is your favorite food?',
            'question-1-label': 'favorite food',
            'question-1-valid_responses': 'mexican, french, italian',
            'question-2-copy': 'Which rock musician?',
            'question-2-label': 'rock musician',
            'question-2-checks_0_0': 'equal',
            'question-2-checks_0_1': 'favorite music',
            'question-2-checks_0_2': 'rock',
            'question-2-checks_1_0': 'not equal',
            'question-2-checks_1_1': 'favorite food',
            'question-2-checks_1_2': 'mexican',
            'completed_response-TOTAL_FORMS': 1,
            'completed_response-INITIAL_FORMS': 0,
            'completed_response-MAX_NUM_FORMS': '',
            'completed_response-0-copy': 'ROCK!!',
            'completed_response-0-checks_0_0': 'equal',
            'completed_response-0-checks_0_1': 'favorite music',
            'completed_response-0-checks_0_2': 'rock',
        })
        uid = self.poll_manager.get_latest_uid(self.poll_id)
        poll = self.poll_manager.get(self.poll_id, uid)
        self.assertRedirects(response, reverse('content:formset', kwargs={
            'poll_id': self.poll_id,
            }))
        self.assertEqual(len(poll.questions), 3)
        # prime the new participant with some historical data
        participant = self.poll_manager.get_participant(self.poll_id,
                'somemsisdn')
        participant.has_unanswered_question = True
        participant.set_last_question_index(1)

        # These previous questions should trigger the next question
        participant.set_label('favorite music', 'rock')
        participant.set_label('favorite food', 'italian')
        self.poll_manager.save_participant(self.poll_id, participant)
        question = poll.get_next_question(participant)
        self.assertEqual(question.copy, 'Which rock musician?')

        # These previous questions should not trigger the next question
        participant.set_label('favorite music', 'rock')
        participant.set_label('favorite food', 'mexican')
        self.poll_manager.save_participant(self.poll_id, participant)
        question = poll.get_next_question(participant)
        self.assertEqual(question, None)

        c_resp = self.poll_manager.get_completed_response(participant, poll,
            'default response')
        self.assertEqual(c_resp, 'ROCK!!')


