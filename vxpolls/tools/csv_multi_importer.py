# -*- test-case-name: tests.test_tools -*-
import csv
import sys
import yaml
import redis
from vxpolls.manager import PollManager
from twisted.python import usage


class PollImporter(object):

    def __init__(self, config):
        r_config = config.get('redis', {})
        vxp_config = config.get('vxpolls', {})
        poll_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.get_redis(r_config)
        self.pm = PollManager(self.r_server, poll_prefix)

    def get_redis(self, config):
        return redis.Redis(**config)

    def import_data(self, poll_id_prefix,
                    start_number, last_number,
                    template, input_handle):
        # well we don't want to write anything yet
        #self.pm.set(poll_id, config)
        delimiter = template.get('csv_delimiter', ',')
        csv_reader = csv.reader(input_handle,
                                delimiter=delimiter,
                                quoting=csv.QUOTE_MINIMAL)
        row_list = []
        for row in csv_reader:
            row_list.append(row)
            print row
        #print row_list


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-id-prefix", "p", None,
            "The prefix for a series of numbered polls"],
        ["start-number", "s", "1", "The initial poll number [1]"],
        ["last-number", "l", "1", "The final poll number [1]"],
        ["template", "t", None, "A yaml template of a std poll"],
        ["input", "i", None, "Input csv file"],
    ]

    def postOptions(self):
        if not (self['config'] \
                and self['poll-id-prefix'] \
                and self['input']):
            raise usage.UsageError(
                "Please specify --config, --poll-id-prefix and --input")

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

    input_file = options['input']
    input_handle = open(input_file, 'r')

    template = None
    if options['template']:
        template_file = options['template']
        template = yaml.safe_load(open(template_file, 'r'))

    importer = PollImporter(config)
    importer.import_data(options['poll-id-prefix'],
                        int(options['start-number']),
                        int(options['last-number']),
                        template,
                        input_handle,
                        )
