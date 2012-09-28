from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.conf import settings

from vxpolls.content import forms
from vxpolls.manager import PollManager

from vumi.persist.redis_manager import RedisManager

redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)


def show(request, poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
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


def clear_empties(cleaned_data):
    """
    FIXME:  this is a work around because for some reason Django is seeing
            the new (empty) forms in the formsets as stuff that is to be
            stored when it really should be discarded.
    """
    return [cd for cd in cleaned_data if cd.get('copy')]


def formset(request, poll_id):
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    poll_data = pm.get_config(poll_id)
    questions_data = poll_data.get('questions', [])
    completed_response_data = poll_data.get('survey_completed_responses', [])
    if request.method == 'POST':
        # Set the poll_id
        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
            })
        # the questions & the forms are separate objects
        # validate both, then merge the results into a single JSON hash
        # that is stored in Redis
        questions_form = forms.make_form_set(data=post_data)
        completed_response_form = forms.make_completed_response_form_set(
            data=post_data)
        poll_form = forms.PollForm(data=post_data)
        if (questions_form.is_valid() and poll_form.is_valid() and
            completed_response_form.is_valid()):
            data = poll_form.cleaned_data.copy()
            data.update({
                'questions': clear_empties(questions_form.cleaned_data),
                'survey_completed_responses': clear_empties(
                    completed_response_form.cleaned_data),
            })
            pm.set(poll_id, data)
            return redirect(reverse('content:formset', kwargs={
                'poll_id': poll_id,
                }))
    else:
        poll_form = forms.PollForm(initial=poll_data)
        questions_form = forms.make_form_set(initial=questions_data)
        completed_response_form = forms.make_completed_response_form_set(
            initial=completed_response_data)
    return render(request, 'formset.html', {
        'poll_form': poll_form,
        'questions_form': questions_form,
        'completed_response_form': completed_response_form,
        })
