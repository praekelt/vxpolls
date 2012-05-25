# -*- test-case-name: tests.test_tools -*-
import sys
import yaml
import redis
from vxpolls.manager import PollManager
from twisted.python import usage


class PollExporter(object):

    stdout = sys.stdout

    def __init__(self, config):
        r_config = config.get('redis', {})
        poll_prefix = config.get('poll_prefix', 'poll_manager')
        self.r_server = self.get_redis(r_config)
        self.pm = PollManager(self.r_server, poll_prefix)

    def get_redis(self, config):
        return redis.Redis(**config)

    def get_poll_config(self, poll_id):
        uid = self.pm.get_latest_uid(poll_id)
        config = self.pm.get_config(poll_id, uid)
        return config

    def export(self, poll_id):
        if poll_id not in self.pm.polls():
            raise ValueError('Poll does not exist')
        config = self.get_poll_config(poll_id)
        yaml.safe_dump(config, self.stdout)


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-id", "p", None, "The poll-id to export"],
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

    exporter = PollExporter(config)
    exporter.export(options['poll-id'])
