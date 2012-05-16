from django.conf.urls.defaults import patterns, include, url
from vxpolls.djdashboard import views

urlpatterns = patterns('',
    url(r'^$', views.home, name='home'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/$', views.show, name='show'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/results\.json$', views.results, name='results'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/active\.json$', views.active, name='active'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/completed\.json$', views.completed, name='completed'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/results\.csv$', views.export_results, name='export_results'),
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/users\.csv$', views.export_users, name='export_users'),
)
