from datetime import timedelta, datetime
from notify import Emailer
from json import loads, load
from re import match
import requests
from sys import argv, exit
from time import sleep

class JsonSettingsError(Exception):
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

    def start_feed_validation(self, feed):
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
        if (response.status_code == 200):
            response_json = loads(response.text)
            feed.last_polled_validator = datetime.now()
            if (datetime.fromtimestamp(response_json['test-time']) > feed.validation_start_time):
                validation_finished = True
                feed.last_validated = datetime.now()
                feed.validation_start_time = None
                total_issues = int(response_json['total-issue-count'])
        return validation_finished, total_issues == 0, total_issues, response_json

class Feed(object):
    """Represents a Feed as stored in the json settings file"""
    def __init__(self, name, endpoint, username, password, raw_next_try, failure_email):
        super(Feed, self).__init__()
        self.last_validated = None
        self.validation_start_time = None
        self.last_polled_validator = None
        self.name = name
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.failure_email = failure_email
        raw_next_try = raw_next_try

        result = match('^(\d+)([m|M|h|H|d|D])$', raw_next_try)
        if (result):
            duration = int(result.group(1))
            period = result.group(2).lower()

            if (duration == 0):
                raise JsonSettingsError('Invalid next_try value provided. Check your JSON settings.')
            duration_types  = {"m": "minutes", "h": "hours", "d": "days"}
            delta_kwargs = {}
            delta_kwargs[duration_types[period]] = duration
            self.next_try = timedelta(**delta_kwargs)
        else:
            raise JsonSettingsError('Invalid next_try value provided. Check your JSON settings.')

class JsonSettings(object):
    def __init__(self, json_path):
        super(JsonSettings, self).__init__()
        self.json_data = self.load_json_settings(json_path)

    def load_emailer(self):
        return Emailer(self.json_data['email'])

    def load_validator(self):
        """Load a validator from json settings"""
        try:
            validator_data = self.json_data['validator']
            endpoint = validator_data['endpoint']
            username = validator_data['username']
            password = validator_data['password']
            return Validator(endpoint, username, password)
        except KeyError as e:
            raise JsonSettingsError('{0} value is not present. Check your JSON settings.'.format(e))

    def load_feeds(self):
        try:
            feeds_data = self.json_data['feeds']
            feeds = []
            for feed in feeds_data:
                name = feed['name']
                endpoint = feed['endpoint']
                username = feed['username']
                password = feed['password']
                raw_next_try = feed['next_try']
                failure_email = feed['failure_email']
                feeds.append(Feed(name, endpoint, username, password, raw_next_try, failure_email))
            return feeds
        except KeyError as e:
            raise JsonSettingsError('{0} value is not present. Check your JSON settings.'.format(e))

    def load_json_settings(self, json_path):
        try:
            json_file = open(json_path)
        except IOError:
            raise JsonSettingsError('The specified json settings file does not exist: {0}'.format(json_path))
        json_data = load(json_file)
        json_file.close()
        return json_data

def main():
    if (len(argv) >= 2):
        settings_path = argv[1]
    else:
        settings_path = 'settings.json'
    settings = JsonSettings(settings_path)
    validator = settings.load_validator()
    feeds = settings.load_feeds()
    emailer = settings.load_emailer()
    while (True):
        for feed in feeds:
            if (feed.validation_start_time is None and (feed.last_validated is None or feed.last_validated + feed.next_try < datetime.now())):
                validator.start_feed_validation(feed)
            elif (feed.validation_start_time is not None and (feed.last_polled_validator is None or feed.last_polled_validator < datetime.now() - timedelta(minutes = 1))):
                completed, success, total_issues, response_json = validator.poll_results(feed)
                if completed and not success:
                    emailer.send(
                        feed.failure_email,
                        u'Validation Failed For {feed} [{endpoint}] ({total_issues} Issues)'.format(
                            feed = feed.name,
                            endpoint = feed.endpoint,
                            total_issues = total_issues),
                        response_json)

if __name__ == '__main__':
    main()
