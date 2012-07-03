from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('vxpolls.content.views',
    url(r'^(?P<poll_id>[a-zA-Z0-9\-_]+)/$', 'show', name='show'),
    url(r'^formset/(?P<poll_id>[a-zA-Z0-9\-_]+)/$', 'formset', name='formset'),
)
