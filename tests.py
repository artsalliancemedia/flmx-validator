import unittest
from notify import Emailer

class EmailerTests(unittest.TestCase):
    def setUp(self):
        options = {
            "test": True,
            "host": "localhost",
            "port": 25,
            "sender": "flmx-validator@example.com"
        }
        self.emailer = Emailer(options)

    def test_format(self):
        recipients = {
            "to": "test-email@example.com"
        }
        recipient_addrs, message = self.emailer.format(recipients, u"This is the subject!", u"This is the body!")

        self.assertEqual(recipient_addrs, ['test-email@example.com'])

        expected_msg = u"From: flmx-validator@example.com\r\nTo: test-email@example.com\r\nSubject: This is the subject!\r\n\r\nThis is the body!"
        self.assertEqual(message, expected_msg)

if __name__ == '__main__':
    unittest.main()