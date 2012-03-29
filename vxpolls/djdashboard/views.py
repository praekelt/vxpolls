from django.shortcuts import render, Http404
from django.http import HttpResponse
from django.conf import settings
import json
import redis

from vxpolls.manager import PollManager, PollQuestion


vxpolls_redis_config = settings.VXPOLLS_REDIS_CONFIG
# vxpolls_questions = [PollQuestion(idx, **params) for idx, params
#                         in enumerate(settings.VXPOLLS_QUESTIONS)]
redis = redis.Redis(**vxpolls_redis_config)

poll_manager = PollManager(redis, settings.VXPOLLS_PREFIX)

def json_response(obj):
    return HttpResponse(json.dumps(obj), content_type='application/javascript')

def home(request):
    return render(request, 'djdashboard/home.html', {
        'collections': poll_manager.polls(),
    })

def active(request):
    return json_response({
        "item": sorted([
            {
                "label": "Active",
                "value": len(poll_manager.active_participants()),
                "colour": "#4F993C",
            },
            {
                "label": "Inactive",
                "value": len(poll_manager.inactive_participant_user_ids()),
                "colour": "#992E2D",
            },
        ], key=lambda d: d['value'], reverse=True)
    })

def results(request):
    collection_id = request.GET.get('collection_id')
    if collection_id not in settings.VXPOLLS_COLLECTIONS:
        raise Http404('Collection not found')

    question = request.GET['question'].decode('utf8')
    results = results_manager.get_results_for_question(
                                collection_id, question)
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

def completed(request):
    collection_id = request.GET.get('collection_id')
    if collection_id not in settings.VXPOLLS_COLLECTIONS:
        raise Http404('Collection not found')

    collection_results = results_manager.get_results(collection_id)
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

def export_results(request):
    collection_id = request.GET.get('collection_id')
    if collection_id not in settings.VXPOLLS_COLLECTIONS:
        raise Http404('Collection not found')

    results = results_manager.get_results_as_csv(collection_id)
    return HttpResponse(results.getvalue(), content_type='application/csv')

def export_users(request):
    collection_id = request.GET.get('collection_id')
    if collection_id not in settings.VXPOLLS_COLLECTIONS:
        raise Http404('Collection not found')

    results = results_manager.get_users_as_csv(collection_id)
    return HttpResponse(results.getvalue(), content_type='application/csv')