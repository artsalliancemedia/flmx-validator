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

    def validate_feed(self, feed):
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
            success, response = self.poll_validator_results(feed, datetime.now())
            return success, response

    def poll_validator_results(self, feed, query_start_time):
        validator_finished = False
        payload = {
            "validation-type": "all-data",
            "results": feed.endpoint,
            "json": 1,
            }   
        while (True):
            response = requests.get(self.endpoint, auth = (self.username, self.password), params = payload)
            if (response.status_code == 200):
                response_json = loads(response.text)
                if (datetime.fromtimestamp(response_json['test-time']) > query_start_time):
                    feed.last_validated = datetime.now()
                    return int(response_json['total-issue-count']) == 0, response_json
                else:
                    sleep(60)
        
class Feed(object):
    """Represents a Feed as stored in the json settings file"""
    def __init__(self, name, endpoint, username, password, raw_next_try, failure_email):
        super(Feed, self).__init__()
        self.last_validated = None
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
            if (period == 'm'):
                self.next_try = timedelta(minutes = duration)
            elif (period == 'h'):
                self.next_try = timedelta(hours = duration)
            elif (period == 'd'):
                self.next_try = timedelta(days = duration)
        else:
            raise JsonSettingsError('Invalid next_try value provided. Check your JSON settings.')

class JsonSettings(object):
    def __init__(self, json_path):
        super(JsonSettings, self).__init__()
        json_data = self.load_json_settings(json_path)
        self.validator = self.load_validator(json_data)
        self.feeds = self.load_feeds(json_data)
        self.emailer = Emailer(json_data['email'])

    def load_validator(self, json_data):
        """Load a validator from json settings"""
        try:
            validator_data = json_data['validator']
            endpoint = validator_data['endpoint']
            username = validator_data['username']
            password = validator_data['password']
            return Validator(endpoint, username, password)
        except KeyError as e:
            raise JsonSettingsError('{0} value is not present. Check your JSON settings.'.format(e))

    def load_feeds(self, json_data):
        try:
            feeds_data = json_data['feeds']
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
    settings = JsonSettings('settings.json')
    while (True):
        for feed in settings.feeds:
            if (feed.last_validated is None or feed.last_validated + feed.next_try < datetime.now()):
                success, response_json = settings.validator.validate_feed(feed)
                if success == False:
                    emailer.send(feed.failure_email, u'Validation Failed For {feed} [{endpoint}]'.format(feed = feed.name, endpoint = feed.endpoint), response_json)

if __name__ == '__main__':
    main()
