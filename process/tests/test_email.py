from django.test import TestCase
from backend.models import Person
import datetime

class TestEmail(TestCase):
    def setUp(self):
        self.person = Person(cn="Ondřej", sn="Nový", email="ondrej@example.org")
        self.addrstr = "test@example.org"
        self.addrtuple = ("Enric♥ Zìní", "enrico@example.org")
        self.date = datetime.datetime(2017, 6, 5, 4, 3, 2)
        self.args = {
            "from_email": self.person, 
            "to": self.addrstr,
            "cc": [self.person, self.addrstr, self.addrtuple],
            "subject": "♥ Debian ♥",
            "date": self.date,
            "body": "Debian ♥ Debian",
        }

    def test_python(self):
        from process.email import build_python_message
        msg = build_python_message(**self.args)
        lines = msg.as_string().splitlines()
        lines = sorted(lines[:-2]) + lines[-2:]

        self.assertEquals(lines, [
            'Cc: =?utf-8?b?T25kxZllaiBOb3bDvQ==?= <ondrej@example.org>, test@example.org, =?utf-8?b?RW5yaWPimaUgWsOsbsOt?= <enrico@example.org>',
            'Content-Transfer-Encoding: base64',
            'Content-Type: text/plain; charset="utf-8"',
            'Date: Mon, 05 Jun 2017 04:03:02 -0000',
            'From: =?utf-8?b?T25kxZllaiBOb3bDvQ==?= <ondrej@example.org>',
            'MIME-Version: 1.0',
            'Subject: =?utf-8?b?4pmlIERlYmlhbiDimaU=?=',
            'To: test@example.org',
            '',
            'RGViaWFuIOKZpSBEZWJpYW4=',
        ])


    def test_django(self):
        from process.email import build_django_message
        msg = build_django_message(**self.args)
        lines = msg.message().as_string().splitlines()
        # Message-ID is generated nondeterministically: skip it for now
        lines = sorted(line for line in lines[:-2] if not line.startswith("Message-ID")) + lines[-2:]

        self.assertEquals(lines, [
            ' <ondrej@example.org>, test@example.org, =?utf-8?b?RW5yaWPimaU=?=,',
            ' enrico@example.org',
            'Cc: =?utf-8?b?PT91dGYtOD9iP1QyNWt4WmxsYWlCT2IzYkR2UT09Pz0=?=',
            'Content-Transfer-Encoding: base64',
            'Content-Type: text/plain; charset="utf-8"',
            'From: =?utf-8?b?T25kxZllaiBOb3bDvQ==?= <ondrej@example.org>',
            'MIME-Version: 1.0',
            'Subject: =?utf-8?b?4pmlIERlYmlhbiDimaU=?=',
            'To: test@example.org',
            'date: Mon, 05 Jun 2017 04:03:02 -0000',
            '',
            'RGViaWFuIOKZpSBEZWJpYW4=',
        ]) 
