# -*- test-case-name: tests.test_tools -*-
import sys
import yaml
import json

from datetime import datetime

from vumi.persist.redis_manager import RedisManager

from vxpolls.manager import PollManager

from twisted.python import usage


class VxpollExporter(object):

    stdout = sys.stdout

    def __init__(self, config, serializer):
        r_config = config.get('redis_manager', {})
        vxp_config = config.get('vxpolls', {})
        self.poll_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.manager = RedisManager.from_config(r_config)
        self.pm = PollManager(self.r_server, self.poll_prefix)
        self.serializer = serializer

    def export(self, poll_id):
        raise NotImplementedError('Subclasses are to implement this.')


class PollExporter(VxpollExporter):

    def get_poll_config(self, poll_id):
        uid = self.pm.get_latest_uid(poll_id)
        config = self.pm.get_config(poll_id, uid)
        return config

    def export(self, options):
        poll_id = options['poll-id']
        if poll_id not in self.pm.polls():
            raise ValueError('Poll does not exist')
        config = self.get_poll_config(poll_id)
        self.serializer(config, self.stdout)


class ParticipantExporter(VxpollExporter):

    def export(self, options):
        poll_id = options['poll-id']
        poll = self.pm.get(poll_id)
        labels_raw = options.subOptions.get('extra-labels', '').split(',')
        label_key = options.subOptions.get('extra-labels-key', None)
        labels = filter(None, [label.strip() for label in labels_raw])
        questions = [q['label'] for q in poll.questions]
        single_user_id = options.subOptions.get('user-id')
        skip_nones = options.subOptions.get('skip-nones')

        if single_user_id:
            msisdns = [single_user_id]
        else:
            msisdns = self.get_msisdns(poll)

        active, archived = self.split_active_and_archived_msisdns(
            poll, msisdns)

        users = self.get_active_users(poll, active, questions,
                                      label_key, labels, skip_nones)

        if options.subOptions['include-archived']:
            users.extend(self.get_archived_users(poll, archived))

        self.serializer(users, self.stdout)

    def is_archived(self, poll, user_id):
        # bloody multisurvey crap
        poll_id = poll.poll_id.split('_')[0]
        session_key = self.pm.get_session_key(poll_id, user_id)
        archive_key = self.pm.r_key('archive')
        return self.r_server.sismember(archive_key, session_key)

    def split_active_and_archived_msisdns(self, poll, msisdns):
        active = []
        archived = []
        for msisdn in msisdns:
            if self.is_archived(poll, msisdn):
                archived.append(msisdn)
            else:
                active.append(msisdn)
        return active, archived

    def get_msisdns(self, poll):
        keys = self.r_server.keys('%s:poll:results:collections:%s*' % (
            self.poll_prefix, poll.poll_id,))
        return set([key.split(':', 9)[-1] for key in keys])

    def get_active_users(self, poll, msisdns, questions, label_key, labels,
                         skip_nones):
        poll_id = poll.poll_id
        users = [(user_id, user_data) for user_id, user_data in
                 poll.results_manager.get_users(poll_id, questions)
                 if user_id in msisdns]
        for user_id, user_data in users:
            # bloody multisurvey crap
            poll_id = poll.poll_id.split('_')[0]
            timestamp = self.pm.get_participant_timestamp(poll_id, user_id)
            user_data.setdefault('user_timestamp', timestamp.isoformat())

        if labels:
            participant = self.pm.get_participant(label_key, user_id)
            for label in labels:
                value = participant.get_label(label)
                if skip_nones and value is None:
                    continue

                user_data[label] = value
        return users

    def get_archived_users(self, poll, msisdns):
        users = []
        for msisdn in msisdns:
            # bloody multisurvey crap
            poll_id = poll.poll_id.split('_')[0]
            data = self.get_latest_participant_data(
                self.pm.get_archive(poll_id, msisdn))
            users.append((msisdn, data))
        return users

    def get_latest_participant_data(self, archives):
        latest = max(archives, key=lambda participant: participant.updated_at)
        data = latest.labels.copy()
        data['user_timestamp'] = datetime.fromtimestamp(
            latest.updated_at).isoformat()
        return data


class ArchivedParticipantExporter(ParticipantExporter):

    def export(self, options):
        poll_id = options['poll-id']
        single_user_id = options.subOptions.get('user-id')
        if single_user_id:
            users = [(
                single_user_id,
                self.get_latest_participant_data(
                    self.pm.get_archive(poll_id, single_user_id)))]
        else:
            msisdns = self.get_archived_user_ids(poll_id)
            users = []
            for msisdn in msisdns:
                data = self.get_latest_participant_data(
                        self.pm.get_archive(poll_id, msisdn))
                users.append((msisdn, data))
        self.serializer(users, self.stdout)

    def get_archived_user_ids(self, poll_id):
        archive_keys = self.pm.inactive_participant_session_keys()
        return [key.split('-', 3)[-1] for key in archive_keys
                if key.startswith(poll_id)]

    def get_latest_participant_data(self, archives):
        latest = max(archives, key=lambda participant: participant.updated_at)
        data = latest.labels.copy()
        data['user_timestamp'] = datetime.fromtimestamp(
            latest.updated_at).isoformat()
        return data


class ExportPollOptions(usage.Options):
    pass


class ExportParticipantOptions(usage.Options):

    optParameters = [
        ['extra-labels-key', None, None, 'Used for grabbing label values'],
        ['extra-labels', 'l', None,
            'Any extra labels to extract (comma separated)'],
        ['user-id', None, None, 'Extract only for a single user'],
    ]

    optFlags = [
        ['skip-nones', 's', 'Skip None values in the export'],
        ['include-archived', 'i', 'Include archived participants'],
    ]

    def postOptions(self):
        if self['extra-labels'] and not self['extra-labels-key']:
            raise usage.UsageError(
                'Please provide --extra-labels-key when using --extra-labels')


class ExportArchivedParticipantOptions(usage.Options):

    optParameters = [
        ['user-id', None, None, 'Extract only for a single user'],
    ]


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
        ['export-archived-participants', None,
            ExportArchivedParticipantOptions,
            'Export a YAML vspoll participant definition.'],
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
        'export-participants': ParticipantExporter,
        'export-archived-participants': ArchivedParticipantExporter,
    }

    exporter_class = exporter_map.get(options.subCommand)
    if not exporter_class:
        raise usage.UsageError(
            'Please provide a subcommand')

    exporter = exporter_class(config, serializer)
    exporter.export(options)
