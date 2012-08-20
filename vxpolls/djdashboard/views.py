import json
from django.shortcuts import render, Http404
from django.http import HttpResponse
from django.conf import settings

from vxpolls.manager import PollManager

from vumi.persist.redis_manager import RedisManager


redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)

poll_manager = PollManager(redis, settings.VXPOLLS_PREFIX)

def json_response(obj):
    return HttpResponse(json.dumps(obj), content_type='application/javascript')

def home(request):
    return render(request, 'djdashboard/home.html', {
        'poll_ids': poll_manager.polls(),
    })

def show(request, poll_id):
    return render(request, 'djdashboard/show.html', {
        'poll_id': poll_id,
        'poll': poll_manager.get(poll_id)
    })

def active(request, poll_id):
    return json_response({
        "item": sorted([
            {
                "label": "Active",
                "value": len(poll_manager.active_participants(poll_id)),
                "colour": "#4F993C",
            },
            {
                "label": "Inactive",
                "value": len(poll_manager.inactive_participant_user_ids()),
                "colour": "#992E2D",
            },
        ], key=lambda d: d['value'], reverse=True)
    })

def results(request, poll_id):
    if poll_id not in poll_manager.polls():
        raise Http404('Poll not found')

    poll = poll_manager.get(poll_id)
    question = request.GET['question'].decode('utf8')
    results = poll.results_manager.get_results_for_question(
                                poll_id, question)
    return json_response({
        "type": "standard",
        "percentage": "hide",
        "item": sorted([
            {
                "label": l.title(),
                "value": v
            } for l, v in results.items()
        ], key=lambda d: d['value'], reverse=True)
    })

def completed(request, poll_id):
    if poll_id not in poll_manager.polls():
        raise Http404('Poll not found')

    poll = poll_manager.get(poll_id)
    collection_results = poll.results_manager.get_results(poll_id)
    results = collection_results.get('completed', {})
    return json_response({
        "item": sorted([
            {
                "label": "Complete",
                "value": results.get("yes", 0),
                "colour": "#4F993C",
            },
            {
                "label": "Incomplete",
                "value": results.get("no", 0),
                "colour": "#992E2D",
            }
        ], key=lambda d: d['value'], reverse=True)
    })

def export_results(request, poll_id):
    if poll_id not in poll_manager.polls():
        raise Http404('Poll not found')

    poll = poll_manager.get(poll_id)
    results = poll.results_manager.get_results_as_csv(poll_id)
    return HttpResponse(results.getvalue(), content_type='application/csv')

def export_users(request, poll_id):
    if poll_id not in poll_manager.polls():
        raise Http404('Poll not found')

    poll = poll_manager.get(poll_id)
    results = poll.results_manager.get_users_as_csv(poll_id)
    return HttpResponse(results.getvalue(), content_type='application/csv')
