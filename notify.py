import smtplib

class Emailer:
    def __init__(self, settings):
        # Don't open up a smtp connection if we're just running the tests.
        if 'test' not in settings:
            # Set up a connection to the SMTP server.
            if 'ssl' in settings and 'enabled' in settings['ssl'] and settings['ssl']['enabled']:
                self.server = smtplib.SMTP_SSL(host=settings['host'], port=settings['port'], keyfile=settings['ssl']['key'], certfile=settings['ssl']['cert'])
            else:
                self.server = smtplib.SMTP(host=settings['host'], port=settings['port'])

        self.sender = settings['sender']

    def __exit__(self):
        self.server.quit()

    # Put in this method so it's easier to test our code is working in an automated fashion.
    def format(self, recipients, subject, body):
        message = u"From: {from_addr}\r\n".format(from_addr=self.sender)

        if not set.intersection(set(recipients.keys()), set(['to', 'cc', 'bcc'])):
            raise Exception("Must supply either a 'to', 'cc' or 'bcc' to send an email.")

        for cat in recipients:
            # First cast any strings passed in to arrays of strings.
            if not isinstance(recipients[cat], list):
                # Strip out any spaces for niceity.
                recipients[cat] = [x.strip() for x in recipients[cat].split(',')]

            # 'bcc' is not included in the message bit apparently so skip.
            if not cat.lower() == 'bcc':
                # Join the recipients with commas because the message format requires that!
                message += u"{cat}: {recipients}\r\n".format(cat=cat.title(), recipients=u", ".join(recipients[cat]))

        message += u"Subject: {subject}\r\n\r\n{body}".format(subject=subject, body=body)

        # Concat the recipients together, smtp doesn't care what types they are.
        recipient_addrs = [x for sublist in recipients.itervalues() for x in sublist]

        return recipient_addrs, message

    def send(self, recipients, subject, body):
        recipient_addrs, message = self.format(recipients, subject, body)
        self.server.sendmail(self.sender, recipient_addrs, message)

# def main():
#     options = {
#         "host": "aam-ex-1.aam.local",
#         "port": 25,
#         "sender": "flmx-validator@artsalliancemedia.com"
#     }
#     emailer = Emailer(options)
#     emailer.send({'to': 'alex.latchford@artsalliancemedia.com'}, 'This is the subject!', 'This is the body!')

#     print "Email sent!"

# if __name__ == '__main__':
#     main()
