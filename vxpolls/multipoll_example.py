# -*- test-case-name: tests.test_multipull_example -*-
# -*- coding: utf8 -*-


from vumi.tests.utils import FakeRedis
#from vumi.application.base import ApplicationWorker
from vxpolls.example import PollApplication

from vxpolls import PollManager


class MultiPollApplication(PollApplication):

    registertration_partial_response = ''

    registertration_completed_response = ''

    batch_completed_response = 'You have completed the first batch of '\
                                'this weeks questions, dial in again to complete '\
                                'the rest.'
    survey_completed_response = 'You have completed this weeks questions '\
                                'please dial in again next week for more.'
