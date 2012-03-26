from django.conf.urls.defaults import patterns, include, url
from vxpolls.djdashboard import views

urlpatterns = patterns('',
    url(r'^$', views.home, name='home'),
    url(r'^results\.json$', views.results, name='results'),
    url(r'^active\.json$', views.active, name='active'),
    url(r'^completed\.json$', views.completed, name='completed'),
    url(r'^results\.csv$', views.export_results, name='export_results'),
    url(r'^users\.csv$', views.export_users, name='export_users'),
)
