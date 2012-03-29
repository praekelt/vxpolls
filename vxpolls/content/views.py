import yaml
from django.shortcuts import render
from vxpolls.content import forms


def home(request):
    config = yaml.load(open('../poll.yaml', 'r').read())
    if request.POST:
        form = forms.make_form(data=config, initial=config)
        if form.is_valid():
            print form.cleaned_data
        else:
            print form.errors
    else:
        form = forms.make_form(initial=config)
    return render(request, 'home.html', {
        'form': form,
    })