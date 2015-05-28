import django.contrib.auth.backends
import django.contrib.auth.middleware
from django.conf import settings
from collections import namedtuple

# Name the various bits of information DACS gives us
DACSInfo = namedtuple('DACSInfo', ('federation', 'unknown1', "jurisdiction", "username"))

TEST_REMOTE_USER = getattr(settings, "DACS_TEST_USERNAME", None)

def _clean_dacs_username(username):
    """
    Map usernames from DACS to usernames in our auth database
    """
    # Take the username out of DACS parts
    info = DACSInfo(*username.split(":"))
    if '@' in info.username:
        return info.username
    else:
        return info.username + "@debian.org"

class DACSRemoteUserMiddleware(django.contrib.auth.middleware.RemoteUserMiddleware):
    header = 'REMOTE_USER'

    def process_request(self, request):
        from django.contrib import auth
        from django.core.exceptions import ImproperlyConfigured

        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteUserMiddleware class.")

        # Allow to force a DACS user string during testing
        if TEST_REMOTE_USER is not None:
            request.META[self.header] = TEST_REMOTE_USER

        try:
            dacs_user = request.META[self.header]
        except KeyError:
            request.sso_username = None
            # If specified header doesn't exist then return (leaving
            # request.user set to AnonymousUser by the
            # AuthenticationMiddleware).

            # Actually, make really sure we are logged out!
            # See django bug #17869
            if request.user.is_authenticated():
                auth.logout(request)
            return

        if "enrico" in dacs_user:
            auth.logout(request)
            return

        request.sso_username = _clean_dacs_username(dacs_user)

        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.
        if request.user.is_authenticated():
            if request.user.username == self.clean_username(dacs_user, request):
                return
            else:
                # sso username does not match the current person: we may have
                # an invalid entry in the browser session. Force a new login.
                auth.logout(request)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(remote_user=dacs_user)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)
        else:
            # Actually, make really sure we are logged out!
            # FIXME: do we need to file a django bug for this case as well?
            if request.user.is_authenticated():
                auth.logout(request)

class DACSUserBackend(django.contrib.auth.backends.RemoteUserBackend):
    """
    RemoteUserBackend customised to create User objects from Person
    """

    def clean_username(self, username):
        """
        Map usernames from DACS to usernames in our auth database
        """
        return _clean_dacs_username(username)
