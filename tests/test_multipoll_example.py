from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase

from vxpolls.multipoll_example import MultiPollApplication


class MultiPollApplicationTestCase(ApplicationTestCase):

    application_class = MultiPollApplication

    timeout = 1
    poll_ids = ['register', 'week1', 'week2', 'week3']
    default_questions_dict = {
            'register': [{
                'copy': 'What is your name?',
                'valid_responses': [],
                },
                {
                'copy': 'Orange, Yellow or Black?',
                'valid_responses': ['orange', 'yellow', 'black'],
                },
                {
                'copy': 'What is your favorite fruit?',
                'valid_responses': ['apple', 'orange'],
                }],
            'week1': [],
            'week2': [],
            'week3': [],
            }

    def test_pass(self):
        pass
