from datetime import timedelta, datetime
from json import loads, load
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
	def __init__(self, name, endpoint, username, password, raw_next_try):
		super(Feed, self).__init__()
		self.last_validated = None
		self.name = name
		self.endpoint = endpoint
		self.username = username
		self.password = password
		raw_next_try = raw_next_try

		result = match('^(\d+)([m|M|h|H|d|D])$', raw_next_try)
		if (result):
			duration = int(result.group(1))
			period = result.group(2).lower()
			
			if (duration == 0):
				raise Exception('Invalid next_try value provided. Check your JSON settings.')
			if (period == 'm'):
				self.next_try = timedelta(minutes  =duration)
			elif (period == 'h'):
				self.next_try = timedelta(hours = duration)
			elif (period == 'd'):
				self.next_try = timedelta(days = duration)
		else:
			raise Exception('Invalid next_try value provided. Check your JSON settings.')

def main():
    json_data = load_json_settings()
    validator = load_validator(json_data)
    feeds = load_feeds(json_data)
    while (True):
	    for feed in feeds:
			if (feed.last_validated is None or feed.last_validated + feed.next_try < datetime.now()):
				success, response_json = validator.validate_feed(feed)			
				if success == False:
					print "errors!"
	    			#notify of error

def load_validator(json_data):
	"""Load a validator from json settings"""
	try:
		validator_data = json_data['validator']
		endpoint = validator_data['endpoint']
		username = validator_data['username']
		password = validator_data['password']		
	except KeyError as e:
		print '{0} value is not present. Check your JSON settings.'.format(e)
		exit()
	return Validator(endpoint, username, password)

def load_feeds(json_data):
	try:
		feeds_data = json_data['feeds']
	except KeyError as e:
		print '{0} value is not present. Check your JSON settings.'.format(e)
		exit()
	feeds = []
	for feed in feeds_data:		
		name = feed['name']
		endpoint = feed['endpoint']
		username = feed['username']
		password = feed['password']
		raw_next_try = feed['next_try']
		feeds.append(Feed(name, endpoint, username, password, raw_next_try))
	return feeds
    
def load_json_settings():
	file_path = argv[1]	    
	try:
		json_file = open(file_path)
	except IOError:
		print 'The specified json settings file does not exist: {0}'.format(file_path)
		exit()
	json_data = load(json_file)
	json_file.close()
	return json_data

if __name__ == '__main__':
	if (len(argv) == 1):
		print "Usage: app.py path_to_json_settings"
	else:
		main()
