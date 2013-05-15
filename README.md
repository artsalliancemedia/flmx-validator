## FLM-x Feed Validator

Takes a list of [FLM-x](http://flm.foxpico.com/) endpoints and goes through each validating each site in turn sending you a digest failure email periodically.

### Installation

Python 2.6.x is required, pip is useful or look in the requirements.txt to grab the dependencies.

`pip install -r requirements.txt`

### Next Steps

Take a copy of `settings-template.json`, name it `settings.json` and fill out the fields. Please make sure to change the value of `next_try`, this field determines when a feed should next be validated after a successful one, it's either in days, hours or minutes.

By default, the application will use this `settings.json` file, however you can override this by providing a file path as a command line argument.

To start the app run:
`python app.py </example/required/settings.json> [/example/optional/log.out]`

### Tests

They use `unittest` so should be installed if you have python, to run them the command you need is: `python tests.py`