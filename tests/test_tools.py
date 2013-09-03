import yaml
import iso8601
from StringIO import StringIO

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from vumi.tests.utils import PersistenceMixin

from vxpolls.tools.exporter import (
    PollExporter, ParticipantExporter, ArchivedParticipantExporter)
from vxpolls.tools.importer import PollImporter
from vxpolls.manager import PollManager


class FakeOptions(object):

    def __init__(self, options, subOptions=None):
        self.options = options
        self.subOptions = subOptions

    def __getitem__(self, key):
        return self.options.get(key)


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
        self.exporter.export(FakeOptions({'poll-id': 'poll-id-1'}))
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

        self.exporter.export(FakeOptions(
            options={'poll-id': self.poll_id},
            subOptions={'include-archived': False}))

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))
        # check we have all known users
        self.assertEqual(sorted(exported_data.keys()), ['user-1', 'user-2'])
        # check we have all known answers
        self.assertEqual(exported_data['user-1']['the-question'], 'one')
        self.assertEqual(exported_data['user-2']['the-question'], 'two')
        # check we have all timestamps
        self.assertTrue(
            iso8601.parse_date(exported_data['user-1']['user_timestamp']))
        self.assertTrue(
            iso8601.parse_date(exported_data['user-2']['user_timestamp']))

    def test_export_with_archives(self):
        p1 = self.manager.get_participant(self.poll_id, 'user-1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)

        p2 = self.manager.get_participant(self.poll_id, 'user-2')
        question = self.poll.get_next_question(p2)
        self.poll.set_last_question(p2, question)

        p3 = self.manager.get_participant(self.poll_id, 'user-3')
        question = self.poll.get_next_question(p3)
        self.poll.set_last_question(p3, question)

        self.poll.submit_answer(p1, 'one')
        self.poll.submit_answer(p2, 'two')
        self.poll.submit_answer(p3, 'two')

        self.manager.archive(self.poll_id, p3)

        self.exporter.export(FakeOptions(
            options={'poll-id': self.poll_id},
            subOptions={'include-archived': True}))

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))
        # check we have all known users
        self.assertEqual(
            sorted(exported_data.keys()),
            ['user-1', 'user-2', 'user-3'])
        # check we have all known answers
        self.assertEqual(exported_data['user-1']['the-question'], 'one')
        self.assertEqual(exported_data['user-2']['the-question'], 'two')
        self.assertEqual(exported_data['user-3']['the-question'], 'two')
        # check we have all timestamps
        self.assertTrue(
            iso8601.parse_date(exported_data['user-1']['user_timestamp']))
        self.assertTrue(
            iso8601.parse_date(exported_data['user-2']['user_timestamp']))
        self.assertTrue(
            iso8601.parse_date(exported_data['user-3']['user_timestamp']))

    def test_export_with_extra_labels(self):
        p1 = self.manager.get_participant(self.poll_id, 'user-1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)
        self.poll.submit_answer(p1, 'one')

        self.exporter.export(FakeOptions(
            options={'poll-id': self.poll_id},
            subOptions={
                'extra-labels': 'foo, bar, baz',
                'extra-labels-key': self.poll_id,
                'include-archived': False
            }))

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))

        data = exported_data['user-1']
        self.assertEqual(
            set(data.keys()),
            set(['foo', 'bar', 'baz', 'the-question', 'user_timestamp']))

    def test_export_for_a_single_user(self):
        p1 = self.manager.get_participant(self.poll_id, 'user-1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)
        self.poll.submit_answer(p1, 'one')

        p2 = self.manager.get_participant(self.poll_id, 'user-2')
        question = self.poll.get_next_question(p2)
        self.poll.set_last_question(p2, question)
        self.poll.submit_answer(p2, 'two')

        self.exporter.export(FakeOptions(
            options={'poll-id': self.poll_id},
            subOptions={
                'extra-labels': 'foo, bar, baz',
                'extra-labels-key': self.poll_id,
                'user-id': 'user-1',
                'include-archived': False,
            }))

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))

        self.assertEqual(exported_data.keys(), ['user-1'])
        data = exported_data['user-1']
        self.assertEqual(
            set(data.keys()),
            set(['foo', 'bar', 'baz', 'the-question', 'user_timestamp']))

    def test_skip_nones(self):
        p1 = self.manager.get_participant(self.poll_id, 'user-1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)
        self.poll.submit_answer(p1, 'one')

        self.exporter.export(FakeOptions(
            options={'poll-id': self.poll_id},
            subOptions={
                'skip-nones': True,
                'extra-labels': 'foo, bar, baz',
                'extra-labels-key': self.poll_id,
                'user-id': 'user-1',
                'include-archived': False,
            }))

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))

        self.assertEqual(exported_data.keys(), ['user-1'])
        data = exported_data['user-1']
        self.assertEqual(
            set(data.keys()),
            set(['the-question', 'user_timestamp']))


class ArchivedParticipantExportTestCase(PersistenceMixin, TestCase):

    @inlineCallbacks
    def setUp(self):
        yield self._persist_setUp()
        self.poll_prefix = 'poll_prefix'
        config = self.mk_config({
            'vxpolls': {
                'prefix': self.poll_prefix,
            },
        })
        self.normal_exporter = ParticipantExporter(config, yaml.safe_dump)
        self.exporter = ArchivedParticipantExporter(config, yaml.safe_dump)
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

    def test_export_archives_single_user(self):
        p1 = self.manager.get_participant(self.poll_id, 'user1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)

        p2 = self.manager.get_participant(self.poll_id, 'user2')
        question = self.poll.get_next_question(p2)
        self.poll.set_last_question(p2, question)

        self.poll.submit_answer(p1, 'one')
        self.poll.submit_answer(p2, 'two')

        # archive!
        self.manager.archive(self.poll_id, p1)
        self.manager.archive(self.poll_id, p2)

        options = FakeOptions(
            options={
                'poll-id': self.poll_id
            },
            subOptions={
                'user-id': 'user1'
            })
        self.exporter.export(options)

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))
        # check we have all known users
        self.assertEqual(sorted(exported_data.keys()), ['user1'])
        # check we have all known answers
        self.assertEqual(exported_data['user1']['the-question'], 'one')
        # check we have all timestamps
        self.assertTrue(
            iso8601.parse_date(exported_data['user1']['user_timestamp']))

    def test_export_archives(self):
        p1 = self.manager.get_participant(self.poll_id, 'user1')
        question = self.poll.get_next_question(p1)
        self.poll.set_last_question(p1, question)

        p2 = self.manager.get_participant(self.poll_id, 'user2')
        question = self.poll.get_next_question(p2)
        self.poll.set_last_question(p2, question)

        self.poll.submit_answer(p1, 'one')
        self.poll.submit_answer(p2, 'two')

        # archive!
        self.manager.archive(self.poll_id, p1)
        self.manager.archive(self.poll_id, p2)

        options = FakeOptions(
            options={
                'poll-id': self.poll_id
            },
            subOptions={})
        self.exporter.export(options)

        exported_string = self.exporter.stdout.getvalue()
        exported_data = dict(yaml.safe_load(exported_string))
        # check we have all known users
        self.assertEqual(sorted(exported_data.keys()), ['user1', 'user2'])
        # check we have all known answers
        self.assertEqual(exported_data['user1']['the-question'], 'one')
        self.assertEqual(exported_data['user2']['the-question'], 'two')
        # check we have all timestamps
        self.assertTrue(
            iso8601.parse_date(exported_data['user1']['user_timestamp']))
        self.assertTrue(
            iso8601.parse_date(exported_data['user2']['user_timestamp']))
