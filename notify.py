import smtplib

class NotifyError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Emailer:
    def __init__(self, settings):
        self.host = settings['host']
        self.port = settings['port']
        self.ssl_enabled = False
        if 'ssl' in settings and 'enabled' in settings['ssl'] and settings['ssl']['enabled']:
            self.ssl_enabled = True
            self.key_file = settings['ssl']['key']
            self.certificate = settings['ssl']['cert']
        self.sender = settings['sender']

    # Put in this method so it's easier to test our code is working in an automated fashion.
    def format(self, recipients, subject, body):
        message = u"From: {from_addr}\r\n".format(from_addr=self.sender)

        if not isinstance(recipients, dict) or not set.intersection(set(recipients.keys()), set(['to', 'cc', 'bcc'])):
            raise NotifyError("Must supply either a 'to', 'cc' or 'bcc' to send an email.")

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

    def connect(self):
        if self.ssl_enabled:
            self.server = smtplib.SMTP_SSL(host=self.host, port=self.port, keyfile=self.key_file, certfile=self.certificate)
        else:
            self.server = smtplib.SMTP(host=self.host, port=self.port)

    def send(self, recipients, subject, body):
        recipient_addrs, message = self.format(recipients, subject, body)
        self.connect()
        self.server.sendmail(self.sender, recipient_addrs, message)
        self.server.quit()