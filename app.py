from datetime import timedelta, datetime
from notify import Emailer
from json import loads, load
from jsonschema import validate
from re import match
import requests
from sys import argv, exit
from time import sleep

class Validator(object):
    """Represents a Validator as stored in the json settings file"""
    def __init__(self, endpoint, username, password):
        super(Validator, self).__init__()
        self.endpoint = endpoint
        self.username = username
        self.password = password

    def start(self, feed):
        payload = {
            "url": feed.endpoint,
            "username": feed.username,
            "password": feed.password,
            "which-checks": "read-only",
            "validation-type": "all-data",
            }
        try:
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
        response = requests.get(self.endpoint, auth = (self.username, self.password), params = payload)
        if response.status_code == 200:
            response_json = loads(response.text)
            feed.last_polled_validator = datetime.now()
            if datetime.fromtimestamp(response_json['test-time']) > feed.validation_start_time:
                validation_finished = True
                feed.last_validated = datetime.now()
                feed.validation_start_time = None
                total_issues = int(response_json['total-issue-count'])
        return validation_finished, total_issues == 0, total_issues, response_json

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
                raise ValueError('Invalid next_try value provided. Check your JSON settings.')
            duration_types  = {"m": "minutes", "h": "hours", "d": "days"}
            delta_kwargs = {}
            delta_kwargs[duration_types[period]] = duration
            self.next_try = timedelta(**delta_kwargs)
        else:
            raise ValueError('Invalid next_try value provided. Check your JSON settings.')

class JsonSettings(object):
    def __init__(self, json_path):
        super(JsonSettings, self).__init__()
        self.json_data = self.load(json_path)
        self.validate()

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

def main():
    if len(argv) >= 2:
        settings_path = argv[1]
    else:
        settings_path = 'settings.json'
    settings = JsonSettings(settings_path)
    validator = Validator(**settings.json_data['validator'])
    feeds = load_feeds(settings.json_data)
    emailer = Emailer(settings.json_data['email'])
    while (True):
        for feed in feeds:
            if feed.validation_start_time is None and (feed.last_validated is None or feed.last_validated + feed.next_try < datetime.now()):
                validator.start_feed_validation(feed)
            elif feed.validation_start_time is not None and (feed.last_polled_validator is None or feed.last_polled_validator < datetime.now() - timedelta(minutes = 1)):
                completed, success, total_issues, response_json = validator.poll_results(feed)
                if completed and not success:
                    emailer.send(
                        feed.failure_email,
                        u'Validation Failed For {feed} [{endpoint}] ({total_issues} Issues)'.format(
                            feed = feed.name,
                            endpoint = feed.endpoint,
                            total_issues = total_issues),
                        response_json)

def load_feeds(json_data):
    feeds_data = json_data['feeds']
    feeds = []
    for feed in feeds_data:
        feeds.append(Feed(**feed))
    return feeds

if __name__ == '__main__':
    main()