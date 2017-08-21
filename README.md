Debian NM Front Desk web application
====================================

## Running this code on your own machine
### Dependencies

    apt-get install python3-markdown python3-ldap python3-psycopg2 python3-xapian \
     python3-django python3-django-housekeeping \
     python3-debian python3-debiancontributors

### Configuration

    mkdir data # required by default settings
    cd nm2
    ln -s local_settings.py.devel local_settings.py
    edit local_settings.py as needed

### First setup
    
    ./manage.py migrate

### Fill in data
Visit https://nm.debian.org/am/db-export to download nm-mock.json; for privacy,
sensitive information are replaced with mock strings.

If you cannot login to the site, you can ask any DD to download it for you.
There is nothing secret in the file, but I am afraid of giving out convenient
email databases to anyone.

    ./manage.py import nm-mock.json

If you are a Front Desk member or a DAM, you can use
https://nm.debian.org/am/db-export?full for a full database export.

### Sync keyrings
    rsync -az --progress keyring.debian.org::keyrings/keyrings/  ./data/keyrings/

### Run database maintenance
    
    ./manage.py housekeeping

### Run the web server
    
    ./manage.py runserver


## Periodic updates
You need to run periodic maintenance to check/regenerate the denormalised
fields:

    ./manage.py housekeeping


## Development
Development targets Django 1.8, although the codebase has been created with
Django 1.2 and it still shows in some places. Feel free to cleanup.

Unusual things in the design:

* `backend/` has the core models. Note that `backend.models.Process` is the
  old-style workflow, and `process.model.Process` is the new style workflow.
* there is a custom permission system with a class hierarchy that starts at
  `backend.models.VisitorPermissions`, and that generates a set of permission
  strings that get tested in views and templates with things like `if
  "edit_bio" in visit_perms: …`.
* `backend.mixins.VisitorMixin` is the root of a class hierarchy of mixins used
  by most views in the site; those mixins implement the basis of resource
  instantiation and permission checking.
