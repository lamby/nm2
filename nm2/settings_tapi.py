# Settings module for test-archive-process-email
# It deletes minechangelogs because it's not needed, and it needs
# python3-xapian which does not exist yet (#647441)

from .settings import *

INSTALLED_APPS.remove("minechangelogs")
