from json import load, dumps
from classes import Feed
from time import sleep
from sys import argv, exit
from re import match
import requests
from datetime import timedelta, datetime
from bs4 import BeautifulSoup

class ValidationResult(object):
	"""docstring for ValidationResult"""
	def __init__(self, result, time, duration, warnings, errors):
		super(ValidationResult, self).__init__()
		self.result = result
		self.time = time
		self.warnings = warnings
		self.errors = errors
		self.total_errors = len(self.errors)
		self.total_warnings = len(self.warnings)
		
class Feed(object):
	"""Represents a Feed as stored in the json settings file"""
	def __init__(self, feed_data, validator):
		super(Feed, self).__init__()
		try:
			self.validator = validator
			self.name = feed_data['name']
			self.endpoint = feed_data['endpoint']
			self.username = feed_data['username']
			self.password = feed_data['password']
			raw_next_try = feed_data['next_try']
		except KeyError as e:
			exit_with_error('Feed {0} value is not present. Check your JSON settings.'.format(e))

		result = match('^(\d+)([m|M|h|H|d|D])$', raw_next_try)
		if (result):
			duration = int(result.group(1))
			period = result.group(2).lower()
			
			if (duration == 0):
				exit_with_error('Invalid next_try value provided. Check your JSON settings.')
			if (period == 'm'):
				self.next_try = timedelta(minutes=duration)
			elif (period == 'h'):
				self.next_try = timedelta(hours=duration)
			elif (period == 'd'):
				self.next_try = timedelta(days=duration)
		else:
			exit_with_error('Invalid next_try value provided. Check your JSON settings.')

	def validate(self):
		payload = {
		"url": self.endpoint,
		"username": feed.username,
		"password": feed.password,
		"which-checks": "read-only",
		"validation-type": "all-data"
		}
		try:
			response = requests.get(feed.validator.endpoint, auth = (feed.validator.username, feed.validator.password), params = payload, timeout=60)
		except requests.exceptions.Timeout: 
			response = poll_validator_results(feed, datetime.now())
		if (response.status_code == 200):
			return parse_validator_response(response.text)

class Validator(object):
	"""Represents a Validator as stored in the json settings file"""
	def __init__(self, validator_data):
		super(Validator, self).__init__()
		try:
			self.endpoint = validator_data['endpoint']
			self.username = validator_data['username']
			self.password = validator_data['password']
		except KeyError as e:
			exit_with_error('Validator {0} value is not present. Check your JSON settings.'.format(e))

def exit_with_error(error):
	"""Informs user of excepted error and then exits"""
	print error
	exit()

def main():
    json_data = load_json_settings()
    validator = load_validator(json_data)
    feeds = load_feeds(json_data, validator)
    results = []
    for feed in feeds:
    	results.append(feed.validate())

def parse_validator_response(response):
	response_soup = BeautifulSoup(response)
	success = False	
	errors = []
	warnings = []
	results_div = response_soup.find("div", {"class":"results"})
	success_div = results_div.find("div", {"class": "validation-summary validation-success"})
	date, duration = parse_response_validation_date(response_soup)
	if (success_div is not None):
		success = True
	else:
		error_items = results_div.findAll("li", {"class": "error"})
		for error in error_items:
			errors.append(''.join(error.findAll(text=True)))
		warning_items = results_div.findAll("li", {"class": "warning"})
		for warning in warning_items:
			warnings.append(''.join(warning.findAll(text=True)))
	return ValidationResult(success, date, duration, warnings, errors)

def parse_response_validation_date(response_soup):
	date_div = response_soup.find("div", {"class": "validation-date"}, text=True)
	duration_match = match("^Validation Duration: (\d\d)\:(\d\d)\:(\d\d).$", date_div['title'])    
	duration = timedelta(hours = int(duration_match.group(1)), minutes = int(duration_match.group(2)), seconds = int(duration_match.group(3)))	
	re_date_string = match("(^\w{3}\s\w{3}\s\d{2}\s\d{4}\s\d{2}:\d{2}:\d{2}\s\w{2})\s\w{3}$", ''.join(date_div.findAll(text=True))).group(1)
	date = datetime.strptime(re_date_string, '%a %b %d %Y %I:%M:%S %p')
	return date, duration

def poll_validator_results(feed, query_start_time):
	# This is a dirty hack to deal with the timezone difference between us and the validator endpoint 
	pdt_query_start_time = query_start_time - timedelta(hours = 8)
	validator_finished = False
	while (True):
		response = get_results(feed)
		response_soup = BeautifulSoup(response.text)
		date, duration = parse_response_validation_date(response_soup)
		if (date > pdt_query_start_time):
			return response
		else:
			sleep(60)

def validate_feed(feed):
	payload = {
		"url": feed.endpoint,
		"username": feed.username,
		"password": feed.password,
		"which-checks": "read-only",
		"validation-type": "all-data"
	}
	try:
		response = requests.get(feed.validator.endpoint, auth = (feed.validator.username, feed.validator.password), params = payload, timeout=60)
	except requests.exceptions.Timeout: 
		response = poll_validator_results(feed, datetime.now())
	if (response.status_code == 200):
		return parse_validator_response(response.text)	

def get_results(feed):
	payload = {
		"validation-type": "all-data",
		"results": feed.endpoint
	}	
	return requests.get(feed.validator.endpoint, auth = (feed.validator.username, feed.validator.password), params = payload)

def load_validator(json_data):
	"""Load a validator from json settings"""
	try:
		validator_data = json_data['validator']
	except KeyError as e:
		exit_with_error('{0} value is not present. Check your JSON settings.'.format(e))

	return Validator(validator_data)

def load_feeds(json_data, validator):
	try:
		feeds_data = json_data['feeds']
	except KeyError as e:
		exit_with_error('{0} value is not present. Check your JSON settings.'.format(e))
	feeds = []
	for feed in feeds_data:
		feeds.append(Feed(feed, validator))
	return feeds
    
def load_json_settings():
	file_path = argv[1]	    
	try:
		json_file = open(file_path)
	except IOError:
		exit_with_error('The specified json settings file does not exist: {0}'.format(file_path))
	json_data = load(json_file)
	json_file.close()
	return json_data

def test_parse():
	html_file = open('error_response.html')
	html = html_file.read()
	html_file.close()
	result = parse_validator_response(html)

if __name__ == '__main__':
	if (len(argv) == 1):
		print "Usage: app.py path_to_json_settings"
	else:
		#test_parse()
		main()
