#!/bin/sh -e

export DJANGO_SETTINGS_MODULE=vxpolls.settings
export PYTHONPATH=.

echo "=== Nuking old .pyc files..."
find vxpolls/ -name '*.pyc' -delete
echo "=== Erasing previous coverage data..."
coverage erase
echo "=== Running Django tests ..."
django-admin.py test vxpolls --with-coverage --cover-package=vxpolls
echo "=== Running trial tests..."
coverage run --include='vxpolls/*' --append --branch `which trial` --reporter=subunit tests | tee results.txt | subunit2pyunit
subunit2junitxml <results.txt >test_results.xml
rm results.txt
echo "=== Processing coverage data..."
coverage xml --omit="ve/src/vumi/*"
echo "=== Checking for PEP-8 violations..."
pep8 --repeat vxpolls | tee pep8.txt
echo "=== Done."
