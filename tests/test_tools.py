import yaml
from StringIO import StringIO

from twisted.trial.unittest import TestCase
from vxpolls.tools.export import PollExporter
from vxpolls.manager import PollManager
from vumi.tests.utils import FakeRedis


class ExportTestCase(TestCase):

    def setUp(self):
        self.r_server = FakeRedis()
        self.poll_prefix = 'poll_prefix'
        self.patch(PollExporter, 'get_redis',
            lambda *a: self.r_server)
        self.exporter = PollExporter({
            'poll_prefix': self.poll_prefix,
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
