import yaml
import iso8601
from StringIO import StringIO

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import PersistenceMixin

from vxpolls.tools.exporter import PollExporter, ParticipantExporter
from vxpolls.tools.importer import PollImporter
from vxpolls.manager import PollManager


class PollExportTestCase(PersistenceMixin, TestCase):

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.poll_prefix = 'poll_prefix'
        self.exporter = PollExporter(self.mk_config({
            'vxpolls': {
                'prefix': self.poll_prefix,
            },
        }), yaml.safe_dump)
        self.exporter.stdout = StringIO()
        self.manager = PollManager(self.exporter.r_server, self.poll_prefix)

    def create_poll(self, poll_id, config):
        self.manager.set(poll_id, config)

    @inlineCallbacks
    def tearDown(self):
        yield self.exporter.pm.stop()
        yield self.manager.stop()
        yield self._persist_tearDown()

    def test_export(self):
        config = {
            'batch_size': None,
            'questions': [{
                'copy': 'one or two?',
                'valid_responses': ['one', 'two']
            }],
            'survey_completed_response': 'Thanks for completing the survey',
            'transport_name': 'vxpolls_transport'
        }
        self.create_poll('poll-id-1', config)
        self.exporter.export('poll-id-1')
        exported_string = self.exporter.stdout.getvalue()
        self.assertEqual(exported_string, yaml.safe_dump(config))


class PollImportTestCase(PersistenceMixin, TestCase):

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.poll_prefix = 'poll_prefix'
        self.importer = PollImporter(self.mk_config({
            'vxpolls': {
                'prefix': self.poll_prefix,
            },
        }))
        self.manager = PollManager(self.importer.r_server, self.poll_prefix)
        self.config = {
            'batch_size': None,
            'questions': [{
                'copy': 'one or two?',
                'valid_responses': ['one', 'two']
            }],
            'survey_completed_response': 'Thanks for completing the survey',
            'transport_name': 'vxpolls_transport'
        }

    @inlineCallbacks
    def tearDown(self):
        yield self.importer.pm.stop()
        yield self.manager.stop()
        yield self._persist_tearDown()

    def test_import(self):
        self.assertEqual(self.manager.polls(), set([]))
        self.importer.import_config('poll-id-1', self.config)
        self.assertEqual(self.manager.polls(), set(['poll-id-1']))

    def test_error_when_poll_exists(self):
        self.importer.import_config('poll-id-1', self.config)
        self.assertRaises(ValueError, self.importer.import_config,
                          'poll-id-1', self.config)

    def test_force_import_when_poll_exists(self):
        self.importer.import_config('poll-id-1', self.config, force=True)
        self.assertRaises(ValueError, self.importer.import_config,
                          'poll-id-1', self.config)
        self.assertEqual(self.manager.polls(), set(['poll-id-1']))


class ParticipantExportTestCase(PersistenceMixin, TestCase):

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.poll_prefix = 'poll_prefix'
        self.exporter = ParticipantExporter(self.mk_config({
            'vxpolls': {
                'prefix': self.poll_prefix,
            },
        }), yaml.safe_dump)
        self.exporter.stdout = StringIO()
        self.manager = PollManager(self.exporter.r_server, self.poll_prefix)
        self.poll_id = 'poll-id-1'
        self.create_poll(self.poll_id, {
            'batch_size': None,
            'questions': [{
                'copy': 'one or two?',
                'label': 'the-question',
                'valid_responses': ['one', 'two']
            }],
            'survey_completed_response': 'Thanks for completing the survey',
            'transport_name': 'vxpolls_transport',
        })
        self.poll = self.manager.get(self.poll_id)

    def create_poll(self, poll_id, config):
        self.manager.set(poll_id, config)

    @inlineCallbacks
    def tearDown(self):
        yield self.exporter.pm.stop()
        yield self.manager.stop()
        yield self._persist_tearDown()

    def test_export(self):
        p1 = self.manager.get_participant(self.poll_id, 'user-1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)

        p2 = self.manager.get_participant(self.poll_id, 'user-2')
        question = self.poll.get_next_question(p2)
        self.poll.set_last_question(p2, question)

        self.poll.submit_answer(p1, 'one')
        self.poll.submit_answer(p2, 'two')
        self.exporter.export(self.poll_id)
        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))
        # check we have all known users
        self.assertEqual(exported_data.keys(), ['user-1', 'user-2'])
        # check we have all known answers
        self.assertEqual(exported_data['user-1']['the-question'], 'one')
        self.assertEqual(exported_data['user-2']['the-question'], 'two')
        # check we have all timestamps
        self.assertTrue(
            iso8601.parse_date(exported_data['user-1']['user_timestamp']))
        self.assertTrue(
            iso8601.parse_date(exported_data['user-2']['user_timestamp']))
