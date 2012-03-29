import redis
import yaml

from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.conf import settings
from vxpolls.content import forms
from vxpolls.manager import PollManager


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)

def show(request, poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    if not pm.polls():
        pm.set(poll_id, settings.VXPOLLS_CONFIG)
    config = pm.get_config(poll_id)
    if request.POST:
        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
            'transport_name': 'vxpolls_transport',
        })
        form = forms.make_form(data=post_data, initial=config)
        if form.is_valid():
            pm.set(poll_id, form.export())
            return redirect(reverse('content:show', kwargs={
                'poll_id': poll_id,
            }))
    else:
        form = forms.make_form(data=config, initial=config)
    return render(request, 'show.html', {
        'form': form,
    })