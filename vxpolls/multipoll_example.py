# -*- test-case-name: tests.test_multipull_example -*-
# -*- coding: utf8 -*-


from vumi.tests.utils import FakeRedis
#from vumi.application.base import ApplicationWorker
from vxpolls.example import PollApplication

from vxpolls import PollManager


class MultiPollApplication(PollApplication):

    registration_partial_response = 'You have done part of the registration '\
                                    'process, dail in again to complete '\
                                    'your registration.'
    registration_completed_response = 'You have completed registration, '\
                                      'dial in again to start the surveys.'

    batch_completed_response = 'You have completed the first batch of '\
                                'this weeks questions, dial in again to '\
                                'complete the rest.'
    survey_completed_response = 'You have completed this weeks questions '\
                                'please dial in again next week for more.'

    def validate_config(self):
        self.questions_dict = self.config.get('questions_dict', {})
        self.r_config = self.config.get('redis_config', {})
        self.batch_size = self.config.get('batch_size', 5)
        self.dashboard_port = int(self.config.get('dashboard_port', 8000))
        self.dashboard_prefix = self.config.get('dashboard_path_prefix', '/')
        self.poll_id_list = self.config.get('poll_id_list',
                                            [self.generate_unique_id()])

    def setup_application(self):
        self.r_server = FakeRedis(**self.r_config)
        self.pm = PollManager(self.r_server)
        if not self.pm.exists(self.poll_id_list):
            for p in self.poll_id_list:
                #print p, self.questions_dict.get(p, [])
                self.pm.register(p, {
                    'questions': self.questions_dict.get(p, []),
                    'batch_size': self.batch_size,
                    })
