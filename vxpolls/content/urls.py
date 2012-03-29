from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('vxpolls.content.views',
    url(r'^$', 'home'),
)
