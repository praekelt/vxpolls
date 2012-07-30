# -*- test-case-name: tests.test_tools -*-
import csv
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

    def export_data(self, poll_id_prefix,
                    start_number, last_number,
                    template, output_handle):
        row_list = []
        # Add the column names as the first row
        row_list.append(template['csv_column_names'])
        i = start_number
        while i <= last_number:
            row_dict = {}
            row_number = i
            #print ">>>>", i
            template_i = yaml.load(yaml.dump(template) % {'poll_number': i})
            #print template_i
            poll_id = "%s%s" % (poll_id_prefix, i)
            #print "#"*11, poll_id
            i += 1
            if poll_id not in self.pm.polls():
                raise ValueError('Poll does not exist')
            else:
                config = self.get_poll_config(poll_id)
                labeled_copy = {}
                for q in config['questions']:
                    labeled_copy[q.get('label')] = q.get('copy')
                #print labeled_copy
                for n, v in enumerate(template['csv_column_names']):
                    if n == 0:
                        row_dict[v] = row_number
                    else:
                        label = "%s%s%s%s%s" % (
                                template['csv_column_names'][0],
                                template['csv_name_connector'],
                                row_number,
                                template['csv_name_connector'],
                                v,
                                )
                        #print label
                        copy = config['questions']
                        row_dict[v] = labeled_copy.get(label)
                # Extract values from row_dict using the values in
                # the first row of the row_list as keys
                cell_list = []
                for x in row_list[0]:
                    cell = row_dict[x]
                    # Try and replace "\r\n" occurences with "\n"
                    try:
                        cell = "\n".join(cell.split("\r\n"))
                    except:
                        pass
                    cell_list.append(cell)
                row_list.append(cell_list)

        #print row_list
        delimiter = template.get('csv_delimiter', ',')
        csv_writer = csv.writer(output_handle,
                                delimiter=delimiter,
                                quoting=csv.QUOTE_MINIMAL)
        for row in row_list:
                csv_writer.writerow(row)


class Options(usage.Options):

    optParameters = [
        ["config", "u", None, "The config file to read"],
        ["poll-id-prefix", "p", None,
            "The prefix for a series of numbered polls"],
        ["start-number", "s", "1", "The initial poll number [1]"],
        ["last-number", "l", "1", "The final poll number [1]"],
        ["template", "t", None, "A yaml template of a std poll"],
        ["output", "o", None, "Output csv file"],
    ]

    def postOptions(self):
        if not (self['config'] \
                and self['poll-id-prefix'] \
                and self['output']):
            raise usage.UsageError(
                "Please specify --config, --poll-id-prefix and --output")

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

    output_file = options['output']
    output_handle = open(output_file, 'w')

    template = None
    if options['template']:
        template_file = options['template']
        template = yaml.safe_load(open(template_file, 'r'))

    exporter = PollExporter(config)
    exporter.export_data(options['poll-id-prefix'],
                        int(options['start-number']),
                        int(options['last-number']),
                        template,
                        output_handle,
                        )
