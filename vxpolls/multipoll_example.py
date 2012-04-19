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
