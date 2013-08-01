# -*- test-case-name: tests.test_tools -*-
import sys
import yaml

from vumi.persist.redis_manager import RedisManager

from vxpolls.manager import PollManager

from twisted.python import usage


class VxpollExporter(object):

    stdout = sys.stdout

    def __init__(self, config, serializer):
        r_config = config.get('redis_manager', {})
        vxp_config = config.get('vxpolls', {})
        poll_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.manager = RedisManager.from_config(r_config)
        self.pm = PollManager(self.r_server, poll_prefix)
        self.serializer = serializer

    def export(self, poll_id):
        raise NotImplementedError('Subclasses are to implement this.')


class PollExporter(VxpollExporter):

    def get_poll_config(self, poll_id):
        uid = self.pm.get_latest_uid(poll_id)
        config = self.pm.get_config(poll_id, uid)
        return config

    def export(self, poll_id):
        if poll_id not in self.pm.polls():
            raise ValueError('Poll does not exist')
        config = self.get_poll_config(poll_id)
        self.serializer(config, self.stdout)


class ParticipantExporter(VxpollExporter):

    def export(self, poll_id):
        poll = self.pm.get(poll_id)
        questions = [q['label'] for q in poll.questions]
        users = poll.results_manager.get_users(poll.poll_id, questions)
        for user_id, user_data in users:
            timestamp = self.pm.get_participant_timestamp(poll.poll_id, user_id)
            user_data.setdefault('user_timestamp', timestamp.isoformat())
        self.serializer(users, self.stdout)


class ExportPollOptions(usage.Options):
    pass


class ExportParticipantOptions(usage.Options):
    pass


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-id", "p", None, "The poll-id to export"],
        ["format", "f", "yaml", "The format to export as"],
    ]

    subCommands = [
        ['export-poll', None, ExportPollOptions,
            "Export a YAML vxpoll definition"],
        ['export-participants', None, ExportParticipantOptions,
            'Export a YAML vxpoll participant definition.'],
    ]

    def postOptions(self):
        if not (self['config'] and self['poll-id']):
            raise usage.UsageError(
                "Please specify both --config and --poll-id")

if __name__ == '__main__':
    options = Options()
    try:
        options.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    config_file = options['config']
    config = yaml.safe_load(open(config_file, 'r'))

    serializer_map = {
        'json': json.dump,
        'yaml': yaml.safe_dump
    }
    serializer = serializer_map.get(options['format'], None)
    if not serializer:
        raise usage.UsageError(
            'Please select one of %s as a format' % (
                ', '.join(serializer_map.keys())))

    exporter_map = {
        'export-poll': PollExporter,
        'export-participants': None,
    }

    exporter_class = exporter_map.get(options.subCommand)
    if not exporter:
        raise usage.UsageError(
            'Please provide a subcommand')

    exporter = exporter_class(config)
    exporter.export(options['poll-id'], serializer)

