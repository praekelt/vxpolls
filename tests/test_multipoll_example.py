from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vxpolls.multipoll_example import MultiPollApplication

class MultiPollApplicationTestCase(ApplicationTestCase):

    application_class = MultiPollApplication
