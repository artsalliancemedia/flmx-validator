import unittest
from notify import Emailer, NotifyError

class EmailerTests(unittest.TestCase):
    def setUp(self):
        options = {
            "test": True,
            "host": "localhost",
            "port": 25,
            "sender": "flmx-validator@example.com"
        }
        self.emailer = Emailer(options)

    def test_recipient_format(self):
        # Test that we require at least one of "to", "cc" or "bcc" to send an email.
        recipients = {"fail": "test-email@example.com"}
        self.assertRaises(NotifyError, self.emailer.format, recipients, u"This is the subject!", u"This is the body!")

    def test_recipient_dict_format(self):
        # Test that recipients must be a dict.
        recipients = "fail"
        self.assertRaises(NotifyError, self.emailer.format, recipients, u"This is the subject!", u"This is the body!")

    def test_basic_format(self):
        # Test the basic case of formatting the email correctly.
        recipients = {"to": "test-email@example.com"}
        recipient_addrs, message = self.emailer.format(recipients, u"This is the subject!", u"This is the body!")

        self.assertEqual(recipient_addrs, ['test-email@example.com'])

        expected_msg = u"From: flmx-validator@example.com\r\nTo: test-email@example.com\r\nSubject: This is the subject!\r\n\r\nThis is the body!"
        self.assertEqual(message, expected_msg)

    def test_advanced_format(self):
        # Make sure we can handle all of the input formats we accept.
        recipients = {
            "to": "test-email@example.com",
            "cc": ["test-email1@example.com", "test-email2@example.com"],
            "bcc": "test-email3@example.com, test-email4@example.com,test-email5@example.com"
        }
        recipient_addrs, message = self.emailer.format(recipients, u"This is the subject!", u"This is the body!")

        expected_recipient_addrs = ['test-email1@example.com', 'test-email2@example.com', 'test-email@example.com', 'test-email3@example.com', 'test-email4@example.com', 'test-email5@example.com']
        self.assertEqual(recipient_addrs, expected_recipient_addrs)

        expected_msg = u"From: flmx-validator@example.com\r\nCc: test-email1@example.com, test-email2@example.com\r\nTo: test-email@example.com\r\nSubject: This is the subject!\r\n\r\nThis is the body!"
        self.assertEqual(message, expected_msg)

if __name__ == '__main__':
    unittest.main()