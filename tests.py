import unittest
from notify import Emailer, NotifyError
from datetime import timedelta
from json import dump, load
from jsonschema import ValidationError
from app import Feed, JsonSettings, write_log_entry, LoggerError
from os import remove, path

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

class FeedTests(unittest.TestCase):

    def test_raw_next_try_minutes(self):
        # Test that the feed correctly recognises a next_try value of 10m as being valid
        f = Feed('name', 'endpoint', 'username', 'password', '10m', {})
        self.assertEqual(f.next_try, timedelta(minutes = 10))

    def test_raw_next_try_hours(self):
        # Test that the feed correctly recognises a next_try value of 10h as being valid
        f = Feed('name', 'endpoint', 'username', 'password', '10h', {})
        self.assertEqual(f.next_try, timedelta(hours = 10))

    def test_raw_next_try_days(self):
        # Test that the feed correctly recognises a next_try value of 10d as being valid
        f = Feed('name', 'endpoint', 'username', 'password', '10d', {})
        self.assertEqual(f.next_try, timedelta(days = 10))

    def test_raw_next_try_invalid_duration(self):
        # Test that the feed correctly recognises a next_try value of 1.2m as being invalid
        self.assertRaises(ValueError, Feed, 'name', 'endpoint', 'username', 'password', '1.2m', {})

    def test_raw_next_try_invalid_period(self):
        # Test that the feed correctly recognises a next_try value of 10s as being invalid
        self.assertRaises(ValueError, Feed, 'name', 'endpoint', 'username', 'password', '10s', {})

class JsonSettingsTests(unittest.TestCase):

    test_settings_file_path = 'test_settings.json'
    invalid_settings_file_path = 'invalid_settings.json'

    def setUp(self):
        with open(self.test_settings_file_path, 'w') as test_settings_file:
            dump(
                {
                    "name": "flmx-validator",
                    "version": "0.0.0",
                    "feeds": [
                        {
                            "name": "flmv",
                            "endpoint": "http://flm.foxpico.com/FLM/",
                            "username": "isdcf",
                            "password": "isdcf",
                            "next_try": "1m",
                            "failure_email": {
                                "to": ["flmx-failures@example.com"]
                            }
                        }
                    ],
                    "validator": {
                        "endpoint": "http://flm.foxpico.com/validator",
                        "username": "isdcf",
                        "password": "isdcf"
                    },
                    "email": {
                        "host": "<SMTP host>",
                        "port": 25,
                        "ssl": {
                            "enabled": False,
                            "key": "<path to key file>",
                            "cert": "<path to cert file>"
                        },
                        "sender": "flmx-validator@example.com"
                    }
                },
                test_settings_file,
                indent=4, 
                separators=(',', ': '),
                sort_keys=True
            )

        with open(self.invalid_settings_file_path, 'w') as invalid_settings_file:
            # This json is missing an endpoint for the validator 
            dump(
                {
                    "name": "flmx-validator",
                    "version": "0.0.0",
                    "feeds": [
                        {
                            "name": "flmv",
                            "endpoint": "http://flm.foxpico.com/FLM/",
                            "username": "isdcf",
                            "password": "isdcf",
                            "next_try": "1m",
                            "failure_email": {
                                "to": ["flmx-failures@example.com"],
                            }
                        }
                    ],
                    "validator": {
                        "username": "isdcf",
                        "password": "isdcf"
                    },
                    "email": {
                        "host": "<SMTP host>",
                        "port": 25,
                        "ssl": {
                            "enabled": False,
                            "key": "<path to key file>",
                            "cert": "<path to cert file>"
                        },
                        "sender": "flmx-validator@example.com"
                    }
                },
                invalid_settings_file,
                indent=4, 
                separators=(',', ': '),
                sort_keys=True
            )

    def tearDown(self):
        remove(self.test_settings_file_path)
        remove(self.invalid_settings_file_path)

    def test_settings_file_not_present(self):
        # Test that an exception is thrown when attempting to load a file that isn't present
        self.assertRaises(IOError, JsonSettings, "this/file/is/not/here.json")

    def test_settings_file_present_and_valid(self):
        # Test that a valid json file can be loaded
        JsonSettings(self.test_settings_file_path)

    def test_settings_file_present_and_not_valid(self):
        # Test that a invalid json file cannot be loaded
        self.assertRaises(ValidationError, JsonSettings, self.invalid_settings_file_path)

class LoggerTests(unittest.TestCase):

    def setUp(self):
        self.test_log_file_path = 'test_log.json'
        self.invalid_log_file_path = 'invalid_log.json'
        self.new_log_file_path = 'new_log.json'
        with open(self.test_log_file_path, 'w') as test_log_file:
            dump(
            {
                "entries": [
                    {
                        "level": "info",
                        "message": "Settings loaded from settings.json",
                        "timestamp": "2013-05-10T10:52:25.580000"
                    },
                    {
                        "level": "info",
                        "message": "Validator at endpoint http://flm.foxpico.com/validator initialised",
                        "timestamp": "2013-05-10T10:52:25.581000"
                    }
                ]
            },
            test_log_file,
            indent=4, 
            separators=(',', ': '),
            sort_keys=True
            )

        with open(self.invalid_log_file_path, 'w') as invalid_log_file:
            # This json is missing a level for the second entry 
            dump(
            {
                "entries": [
                    {
                        "level": "info",
                        "message": "Settings loaded from settings.json",
                        "timestamp": "2013-05-10T10:52:25.580000"
                    },
                    {
                        "message": "Validator at endpoint http://flm.foxpico.com/validator initialised",
                        "timestamp": "2013-05-10T10:52:25.581000"
                    }
                ]
            },
            invalid_log_file,
            indent=4, 
            separators=(',', ': '),
            sort_keys=True
            )

    def test_create_new_log(self):
        if path.isfile(self.new_log_file_path):
            remove(self.test_log_file_path)
        write_log_entry("test message", "debug", log_file_path = self.new_log_file_path)
        with open(self.new_log_file_path, 'r') as test_log_file:
            log = load(test_log_file)
            self.assertEqual(len(log['entries']), 1)

    def test_cannot_write_to_invalid_log(self):
        self.assertRaises(LoggerError, write_log_entry, "test message", "info", log_file_path = self.invalid_log_file_path)

    def test_write_invalid_entry(self):
        self.assertRaises(LoggerError, write_log_entry, "test message", "foobar", log_file_path = self.test_log_file_path)
        with open(self.test_log_file_path, 'r') as test_log_file:
            log = load(test_log_file)
            self.assertEqual(len(log['entries']), 2)

    def test_write_valid_entry(self):
        write_log_entry("test message", "debug", log_file_path = self.test_log_file_path)
        with open(self.test_log_file_path, 'r') as test_log_file:
            log = load(test_log_file)
            self.assertEqual(len(log['entries']), 3)

    def tearDown(self):
        remove(self.test_log_file_path)
        remove(self.invalid_log_file_path)
        if path.isfile(self.new_log_file_path):
            remove(self.new_log_file_path)

if __name__ == '__main__':
    unittest.main()