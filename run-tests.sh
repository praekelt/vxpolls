virtualenv --no-site-packages ve && \
source ve/bin/activate && \
pip install -r requirements.pip && \
DJANGO_SETTINGS_MODULE=vxpolls.settings PYTHONPATH=. trial tests && \
DJANGO_SETTINGS_MODULE=vxpolls.settings PYTHONPATH=. django-admin.py test djdashboard content