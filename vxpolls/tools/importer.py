# -*- test-case-name: tests.test_tools -*-
import sys
import yaml

from vumi.persist.redis_manager import RedisManager

from vxpolls.manager import PollManager

from twisted.python import usage


class PollImporter(object):

    def __init__(self, config):
        r_config = config.get('redis_manager', {})
        vxp_config = config.get('vxpolls', {})
        poll_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.manager = RedisManager.from_config(r_config)
        self.pm = PollManager(self.r_server, poll_prefix)

    def import_config(self, poll_id, config, force=False):
        if poll_id in self.pm.polls() and not force:
            raise ValueError('Poll with %s already exists' % (poll_id,))
        self.pm.set(poll_id, config)


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-config", "pc", None, "The poll file"],
        ["poll-id", "p", None, "The poll-id to export"],
    ]

    optFlags = [
        ['force', 'f', 'Force import, overrides polls if it exists']
    ]

    def postOptions(self):
        if not (self['config'] and self['poll-id'] and self['poll-config']):
            raise usage.UsageError(
                "Please specify --config, --poll-id and --poll-config")

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

    poll_config_file = options['poll-config']
    poll_config = yaml.safe_load(open(poll_config_file, 'r'))

    importer = PollImporter(config)
    importer.import_config(options['poll-id'], poll_config,
        force=options['force'])
