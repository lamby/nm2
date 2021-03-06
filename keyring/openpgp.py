import email
import re

class RFC3156:
    """
    Access data inside OpenPGP MIME emails
    """
    def __init__(self, data):
        self.data = data
        self.message = email.message_from_bytes(self.data)
        self.parsed = self.find_payloads(self.message)

    def find_payloads(self, message):
        # https://tools.ietf.org/html/rfc3156
        # RFC3156 extraction initially taken from http://domnit.org/scripts/clearmime
        # and from http://anonscm.debian.org/cgit/nm/nm.git/tree/bin/dm_verify_application?id=a188cfe89f530c68a2002bb61016cc041848e5f5
        if message.get_content_type() == 'multipart/signed':
            if message.get_param('protocol') == 'application/pgp-signature':
                hashname = message.get_param('micalg').upper()
                if not hashname.startswith('PGP-'):
                    raise RuntimeError("micalg header does not start with PGP-")
                self.text, self.sig = message.get_payload()
                if self.sig.get_content_type() != 'application/pgp-signature':
                    raise RuntimeError("second payload is not an application/pgp-signature payload")
                self.text_data = re.sub(rb"\r?\n", b"\r\n", self.text.as_bytes(False))
                self.sig_data = self.sig.get_payload(None, True)
                if not isinstance(self.sig_data, bytes):
                    raise RuntimeError("signature payload is not a byte string")

                return True
        elif message.is_multipart():
            for message in message.get_payload():
                if self._verify_rfc3156_email(message):
                    return True
            return False
        else:
            return False
