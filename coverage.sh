#!/bin/sh
CMD=python-coverage
MODULES=${@:-"api apikeys backend contributors deblayout dm dsa fprs inconsistencies keyring minechangelogs nmlayout person process projectb public restricted wizard"}
eatmydata $CMD run ./manage.py test $MODULES &&
    $CMD html &&
    sensible-browser htmlcov/index.html
