Debian NM Front Desk web application
====================================

## Running this code on your own machine
### Dependencies

    apt-get install python-markdown python-ldap python-psycopg2 python-xapian \
     python-django python-django-housekeeping \
     python-debian python-debiancontributors

#### django-housekeeping

The ‘python-django-housekeeping’ package is not available in Debian
earlier than Debian Stretch. If you are deploying to a machine running
Debian earlier than Stretch, use the following procedure:

    # https://github.com/spanezz/django-housekeeping
    git clone https://github.com/spanezz/django-housekeeping
      (you can either build the package from it or symlink the module directory
      into the contributors.debian.org sources)

    # build the package
    fakeroot debian/rules clean binary

    # install the package
    dpkg -i  ../python-django-housekeeping_0.1-1_all.deb

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
