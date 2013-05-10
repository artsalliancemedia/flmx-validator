from os import path
from traceback import format_exc
from datetime import timedelta, datetime
from notify import Emailer
from json import loads, load, dump
from jsonschema import validate
from re import match
import requests
from sys import argv, exit
from time import sleep

class LoggerError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Validator(object):
    """Represents a Validator as stored in the json settings file"""
    def __init__(self, endpoint, username, password):
        super(Validator, self).__init__()
        self.endpoint = endpoint
        self.username = username
        self.password = password
        write_log_entry("Validator at endpoint {0} initialised".format(self.endpoint), "debug")

    def start(self, feed):
        payload = {
            "url": feed.endpoint,
            "username": feed.username,
            "password": feed.password,
            "which-checks": "read-only",
            "validation-type": "all-data",
            }
        try:
            write_log_entry("Sending validation request for {feedname} [{endpoint}] to {validator}".format(feedname = feed.name, endpoint = feed.endpoint, validator = self.endpoint), "info")
            # We just assume this is going to timeout and move to polling the results endpoint
            requests.get(self.endpoint, auth = (self.username, self.password), params = payload, timeout = 1)
        except requests.exceptions.Timeout:
            feed.validation_start_time = datetime.now()

    def poll_results(self, feed):
        validation_finished = False
        total_issues = 0
        response_json = None
        payload = {
            "validation-type": "all-data",
            "results": feed.endpoint,
            "json": 1,
            }
        write_log_entry("Polling validation results for {feedname} [{endpoint}] from {validator}".format(feedname = feed.name, endpoint = feed.endpoint, validator = self.endpoint), "info")
        response = requests.get(self.endpoint, auth = (self.username, self.password), params = payload)
        if response.status_code == 200:
            validation_finished, total_issues, response_json = handle_results_response(feed, response)

        return validation_finished, total_issues == 0, total_issues, response_json

    def handle_results_response(self, feed, response):
        response_json = loads(response.text)
        feed.last_polled_validator = datetime.now()
        if datetime.fromtimestamp(response_json['test-time']) > feed.validation_start_time:
            write_log_entry("Validation completed for {feedname} [{endpoint}]".format(feedname = feed.name, endpoint = feed.endpoint), "info")
            validation_finished = True
            feed.last_validated = datetime.now()
            feed.validation_start_time = None
            total_issues = int(response_json['total-issue-count'])

        return validation_finished, total_issues, response_json

class Feed(object):
    """Represents a Feed as stored in the json settings file"""
    def __init__(self, name, endpoint, username, password, next_try, failure_email):
        super(Feed, self).__init__()
        self.last_validated = None
        self.validation_start_time = None
        self.last_polled_validator = None
        self.name = name
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.failure_email = failure_email

        result = match('^(\d+)([m|M|h|H|d|D])$', next_try)
        if result:
            duration = int(result.group(1))
            period = result.group(2).lower()

            if duration == 0:
                raise ValueError('Invalid next_try value provided. Valid format is [delta][m|h|d] (i.e "10m", "3h", "2d")')
            duration_types  = {"m": "minutes", "h": "hours", "d": "days"}
            delta_kwargs = {}
            delta_kwargs[duration_types[period]] = duration
            self.next_try = timedelta(**delta_kwargs)
        else:
            raise ValueError('Invalid next_try value provided. Valid format is [delta][m|h|d] (i.e "10m", "3h", "2d")')
        write_log_entry("Feed at endpoint {0} initialised".format(self.endpoint), "info")

class JsonSettings(object):
    def __init__(self, json_path):
        super(JsonSettings, self).__init__()
        self.json_data = self.load(json_path)
        self.validate()
        write_log_entry("Settings loaded from {0}".format(json_path), "info")

    def validate(self):
        with open("settings.schema.json", "r") as schema_file:
            validate(self.json_data, load(schema_file))

    def load(self, json_path):
        try:
            json_file = open(json_path)
        except IOError:
            raise IOError('The specified json settings file does not exist: {0}'.format(json_path))
        json_data = load(json_file)
        json_file.close()

        return json_data

def write_log_entry(message, level, stack_trace = None, log_file_path = "log.json"):    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message
    }
    if stack_trace is not None:
        entry["stacktrace"] = stack_trace
    try:
        # If file exists, load json from file, validate and append new log entry.
        if path.isfile(log_file_path):
            with open(log_file_path, 'r') as json_file:
                json_log = load(json_file)
                # Validate existing log. If this fails, we cannot safely store new log entries.
                with open("log.schema.json", "r") as schema_file:
                    validate(json_log, load(schema_file))
                json_log['entries'].append(entry)
        # Else create a new json log and store the entry.
        else:
                json_log = { "entries" : [ entry ] }
        # Validate updated log.
        with open("log.schema.json", "r") as schema_file:
            validate(json_log, load(schema_file))
        # Write either the updated or new log back to disk.
        with open(log_file_path, 'w') as json_file:
            dump(
                json_log,
                json_file,
                indent=4,
                separators=(',', ': '),
                sort_keys=True)
    except Exception as e:
        raise LoggerError("Error writing to log file: {0}".format(e))

def main():
    try:
        # Load json settings, either from command line argument or default location.
        if len(argv) >= 2:
            settings_path = argv[1]
        else:
            settings_path = 'settings.json'
        settings = JsonSettings(settings_path)
        # Setup validator, emailer and feeds.
        validator = Validator(**settings.json_data['validator'])
        feeds = load_feeds(settings.json_data)
        emailer = Emailer(settings.json_data['email'])
        # Start validation loop.
        while (True):
            for feed in feeds:
                # If feed is not currently being validated, and it was last validated longer than [next_try] ago, start validation.
                if feed.validation_start_time is None and (feed.last_validated is None or feed.last_validated + feed.next_try < datetime.now()):
                    validator.start_feed_validation(feed)
                # Else if validation is running and we haven't polled the validator for results for at least a minute, poll.
                elif feed.validation_start_time is not None and (feed.last_polled_validator is None or feed.last_polled_validator < datetime.now() - timedelta(minutes = 1)):
                    completed, success, total_issues, response_json = validator.poll_results(feed)
                    # If the process has completed and the result was a failure, send an email notification.
                    if completed and not success:
                        write_log_entry("Validation for {feedname} [{endpoint}] resulted in errors, sending email to {addresses}".format(feedname = feed.name, endpoint = feed.endpoint, addresses = feed.failure_email), "info")
                        emailer.send(
                            feed.failure_email,
                            u'Validation Failed For {feed} [{endpoint}] ({total_issues} Issues)'.format(
                                feed = feed.name,
                                endpoint = feed.endpoint,
                                total_issues = total_issues),
                            response_json)
    except LoggerError as le:
        message = "Logging exception occured: {0}\n\nThe application will now exit.".format(e)
        print message
        exit()
    except Exception as e:
        message = "Fatal exception occured: {0}\n\nThe application will now exit.".format(e)
        print message
        write_log_entry(message, "error", stack_trace = format_exc())
        exit()

def load_feeds(json_data):
    feeds_data = json_data['feeds']
    feeds = []
    for feed in feeds_data:
        feeds.append(Feed(**feed))

    return feeds

if __name__ == '__main__':
    main()