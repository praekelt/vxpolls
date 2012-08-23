import yaml
from StringIO import StringIO

from twisted.trial.unittest import TestCase
from vxpolls.tools.exporter import PollExporter
from vxpolls.tools.importer import PollImporter
from vxpolls.manager import PollManager

from vumi.persist.redis_manager import RedisManager


class ExportTestCase(TestCase):

    def setUp(self):
        self.r_server = RedisManager.from_config({
            'FAKE_REDIS': 'yes'
            })
        self.poll_prefix = 'poll_prefix'
        self.patch(PollExporter, 'get_redis',
            lambda *a: self.r_server)
        self.exporter = PollExporter({
            'vxpolls': {
                'prefix': self.poll_prefix,
            }
        })
        self.exporter.stdout = StringIO()
        self.manager = PollManager(self.r_server, self.poll_prefix)

    def create_poll(self, poll_id, config):
        self.manager.set(poll_id, config)

    def tearDown(self):
        self.exporter.pm.stop()
        self.manager.stop()

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


class ImportTestCase(TestCase):

    def setUp(self):
        self.r_server = RedisManager.from_config({
            'FAKE_REDIS': 'yes'
            })
        self.poll_prefix = 'poll_prefix'
        self.patch(PollImporter, 'get_redis',
            lambda *a: self.r_server)
        self.importer = PollImporter({
            'vxpolls': {
                'prefix': self.poll_prefix,
            }
        })
        self.manager = PollManager(self.r_server, self.poll_prefix)
        self.config = {
            'batch_size': None,
            'questions': [{
                'copy': 'one or two?',
                'valid_responses': ['one', 'two']
            }],
            'survey_completed_response': 'Thanks for completing the survey',
            'transport_name': 'vxpolls_transport'
        }

    def tearDown(self):
        self.importer.pm.stop()
        self.manager.stop()

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
