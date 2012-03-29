import yaml
import redis

from django.shortcuts import render
from django.conf import settings
from vxpolls.content import forms
from vxpolls.manager import PollManager


redis = redis.Redis(**settings.VXPOLLS_REDIS_CONFIG)

def home(request):
    config = yaml.load(open('../poll.yaml', 'r').read())
    if request.POST:
        form = forms.make_form(data=request.POST.copy(), initial=config)
        if form.is_valid():
            pm = PollManager(redis, settings.VXPOLLS_PREFIX)
            pm.set(form.cleaned_data['poll_id'], form.export())
        else:
            print form.errors
    else:
        form = forms.make_form(data=config, initial=config)
    return render(request, 'home.html', {
        'form': form,
    })