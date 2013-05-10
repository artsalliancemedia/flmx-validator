import unittest
from notify import Emailer, NotifyError
from datetime import timedelta, datetime
import time
from json import dump, load, dumps
from jsonschema import ValidationError
from app import Feed, JsonSettings, Validator
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

class ValidatorTests(unittest.TestCase):
    success_json = {
       "test-time" : 0,
       "validation-results" : {
          "warnings" : [],
          "errors" : []
       },
       "total-issue-count" : 0,
       "validation-type" : "all-data",
       "url" : "http://redacted/FLM/",
       "test-duration" : 7
    }
    failure_json = {
        "test-time" : 0,
        "validation-results" : {
            "warnings" : [
                "a warning",
                "another warning"
            ],
            "errors" : [
                "an error"
            ]
        },
       "total-issue-count" : 3,
       "validation-type" : "all-data",
       "url" : "http://redacted/FLM/",
       "test-duration" : 7
    }
    invalid_json = {
        "test-time" : 0,
        "validation-results" : {
            "warnings" : [
                "a warning",
                "another warning"
            ],
            "errors" : [
                "an error"
            ]
        },
       "validation-type" : "all-data",
       "url" : "http://redacted/FLM/",
       "test-duration" : 7
    }
    validator = Validator("endpoint", "username", "password")

    def test_process_not_finished(self):
        feed = Feed('name', 'endpoint', 'username', 'password', '10m', {})
        self.success_json["test-time"] = int(time.time()) - 5000
        feed.validation_start_time = datetime.now()
        validation_finished, total_issues, response_json = self.validator.handle_results_response(feed, dumps(self.success_json))
        self.assertEqual(validation_finished, False)

    def test_process_success_response(self):
        feed = Feed('name', 'endpoint', 'username', 'password', '10m', {})
        feed.validation_start_time = datetime.now() - timedelta(minutes=10)
        self.success_json["test-time"] = int(time.time())
        validation_finished, total_issues, response_json = self.validator.handle_results_response(feed, dumps(self.success_json))
        self.assertEqual(validation_finished, True)
        self.assertEqual(total_issues, 0)

    def test_process_failure_response(self):
        feed = Feed('name', 'endpoint', 'username', 'password', '10m', {})
        feed.validation_start_time = datetime.now() - timedelta(minutes=10)
        self.failure_json["test-time"] = int(time.time())
        validation_finished, total_issues, response_json = self.validator.handle_results_response(feed, dumps(self.failure_json))
        self.assertEqual(validation_finished, True)
        self.assertEqual(total_issues, 3)

    def test_process_invalid_response(self):
        feed = Feed('name', 'endpoint', 'username', 'password', '10m', {})
        feed.validation_start_time = datetime.now() - timedelta(minutes=10)
        self.invalid_json["test-time"] = int(time.time())
        self.assertRaises(ValidationError, self.validator.handle_results_response, feed, dumps(self.invalid_json))

if __name__ == '__main__':
    unittest.main()