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
        vxp_config = config.get('vxpolls', {})
        poll_prefix = vxp_config.get('prefix', 'poll_manager')
        self.r_server = self.get_redis(r_config)
        self.pm = PollManager(self.r_server, poll_prefix)

    def get_redis(self, config):
        return redis.Redis(**config)

    def get_poll_config(self, poll_id):
        uid = self.pm.get_latest_uid(poll_id)
        config = self.pm.get_config(poll_id, uid)
        return config

    def export(self, poll_id_prefix,
                start_number, last_number,
                template, output):
        master_list = []
        master_list.append(template['csv_columns'])
        i = start_number
        while i <= last_number:
            row_dict = {}
            row_number = i
            print ">>>>", i
            template_i = yaml.load(yaml.dump(template) % {'poll_number': i})
            print template_i
            poll_id = "%s%s" % (poll_id_prefix, i)
            print "#"*11, poll_id
            i += 1
            if poll_id not in self.pm.polls():
                raise ValueError('Poll does not exist')
            else:
                config = self.get_poll_config(poll_id)
                labeled_copy = {}
                for q in config['questions']:
                    labeled_copy[q.get('label')] = q.get('copy')
                print labeled_copy
                for n, v in enumerate(template['csv_columns']):
                    if n == 0:
                        row_dict[v] = row_number
                    else:
                        label = "%s%s%s%s%s" % (
                                template['csv_columns'][0],
                                template['csv_connector'],
                                row_number,
                                template['csv_connector'],
                                v,
                                )
                        print label
                        copy = config['questions']
                        row_dict[v] = labeled_copy.get(label)
                l = []
                for x in master_list[0]:
                    l.append(row_dict[x])
                master_list.append(l)

                #yaml.safe_dump(config, self.stdout)
        print master_list
        for r in master_list:
            for c in r:
                if isinstance(c, int) or isinstance(c, float):
                    pass
                else:
                    c = "\n".join(str(c).split("\r\n"))
                output.write("%s%s" % (repr(c), template['csv_separator']))
            output.write("\n")


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-id-prefix", "p", None,
            "The prefix for a series of numbered polls"],
        ["start-number", "i", "1", "The initial poll number [1]"],
        ["last-number", "n", "1", "The final poll number [1]"],
        ["template", "t", None, "A yaml template of a std poll"],
        ["output", "o", None, "Output csv file"],
    ]

    def postOptions(self):
        if not (self['config'] and self['poll-id-prefix']):
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

    template = None
    if options['template']:
        template_file = options['template']
        template = yaml.safe_load(open(template_file, 'r'))

    output = None
    if options['output']:
        output_file = options['output']
        output = open(output_file, 'w')


    exporter = PollExporter(config)
    exporter.export(options['poll-id-prefix'],
            int(options['start-number']),
            int(options['last-number']),
            template,
            output,
            )
