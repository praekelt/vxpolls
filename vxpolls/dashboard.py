# -*- test-case-name: tests.test_dashboard -*-
import json

from twisted.application.service import Service
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web import http
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue


class GeckoboardResourceBase(Resource):

    isLeaf = True

    def __init__(self, poll_manager, results_manager):
        Resource.__init__(self)
        self.poll_manager = poll_manager
        self.results_manager = results_manager

    @inlineCallbacks
    def do_render_GET(self, request):
        json_data = yield self.get_data(request)
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/json")
        request.write(json.dumps(json_data))
        request.finish()

    def render_GET(self, request):
        self.do_render_GET(request)
        return NOT_DONE_YET

    def get_data(self, request):
        raise NotImplementedError("Sub-classes should implement get_data")


class PollResultsResource(GeckoboardResourceBase):

    @inlineCallbacks
    def get_data(self, request):
        collection_id = request.args['collection_id'][0]
        question = request.args['question'][0].decode('utf8')
        results_manager = self.results_manager
        results = yield results_manager.get_results_for_question(
                                    collection_id, question)
        returnValue({
            "type": "standard",
            "percentage": "hide",
            "item": sorted([
                {
                    "label": l.title(),
                    "value": v
                } for l, v in results.items()
            ], key=lambda d: d['value'], reverse=True)
        })


class PollActiveResource(GeckoboardResourceBase):

    @inlineCallbacks
    def get_data(self, request):
        poll_id = request.args['poll_id'][0]
        poll_manager = self.poll_manager
        active_participants = yield poll_manager.active_participants(poll_id)
        active_count = len(active_participants)
        d = poll_manager.inactive_participant_session_keys()
        inactive_participants = yield d
        inactive_count = len(inactive_participants)
        returnValue({
            "item": sorted([
                {
                    "label": "Active",
                    "value": active_count,
                    "colour": "#4F993C",
                },
                {
                    "label": "Inactive",
                    "value": inactive_count,
                    "colour": "#992E2D",
                },
            ], key=lambda d: d['value'], reverse=True)
        })


class PollCompletedResource(GeckoboardResourceBase):

    def get_completed(self, collection_id):
        results_manager = self.results_manager
        results = results_manager.get_results(collection_id)
        return results.get('completed', {})

    def get_data(self, request):
        collection_id = request.args['collection_id'][0]
        results = self.get_completed(collection_id)
        return {
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
        }


class PollResultsCSVResource(Resource):

    isLeaf = True

    def __init__(self, results_manager):
        Resource.__init__(self)
        self.results_manager = results_manager

    @inlineCallbacks
    def do_render_GET(self, request):
        collection_id = request.args['collection_id'][0]
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/csv")
        results = yield self.results_manager.get_results_as_csv(collection_id)
        request.write(results.getvalue())
        request.finish()

    def render_GET(self, request):
        self.do_render_GET(request)
        return NOT_DONE_YET


class PollUsersCSVResource(Resource):

    isLeaf = True

    def __init__(self, results_manager):
        Resource.__init__(self)
        self.results_manager = results_manager

    @inlineCallbacks
    def do_render_GET(self, request):
        collection_id = request.args['collection_id'][0]
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/csv")
        results = yield self.results_manager.get_users_as_csv(collection_id)
        request.write(results.getvalue())
        request.finish()

    def render_GET(self, request):
        self.do_render_GET(request)
        return NOT_DONE_YET


class InstructionsResource(Resource):

    def __init__(self, config):
        Resource.__init__(self)
        self.config = config

    def render_GET(self, request):
        request.write("""
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
   "http://www.w3.org/TR/html4/loose.dtd">

<html lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>vxPolls</title>
    <meta name="generator" content="TextMate http://macromates.com/">
    <meta name="author" content="Simon de Haan">
    <!-- Date: 2011-05-26 -->
    <style type="text/css" media="screen">
       * {
           font-family: Helvetica, sans-serif;
       }

       code {
           font-family: Courier, mono;
           background-color: #999;
           padding: 2px;
       }

       #main {
           width: 572px;
           margin: 100px auto;
       }
    </style>
</head>
<body>
    <div id="main">
        <h1>vxPolls QA instance</h1>
        <p>
            This is a QA version of vxPolls, all content is for testing purposes
            only and are not in anyway related to real people.
        </p>
        <h2>Documentation</h2>
        <div>
            <strong>Dashboard</strong>
            <p>
                We provide a simple HTTP URL for Geckoboard based dashboards. These are the available URLs.
            </p>
            <ul>
                <li><a target="_blank" href="active">Active Participants</a></li>
                <li><a target="_blank" href="completed?collection_id=%(collection_id)s">Completed Surveys</a></li>
                <li><a target="_blank" href="results?collection_id=%(collection_id)s&amp;question=%(question)s">Results for question '%(question)s'</a></li>
            </ul>
            <strong>Data export</strong>
            <ul>
                <li><a href="users.csv?collection_id=%(collection_id)s">User data</a></li>
                <li><a href="results.csv?collection_id=%(collection_id)s">Poll results</a></li>
            </ul>
            <strong>QA via Gtalk</strong>
            <p>
                While the SMS provider and gateway are still in the process of
                being setup, the SMS application can in the mean time be
                tested by using GTalk or any other Jabber/XMPP based chat client
                by following these instructions:
            </p>
            <ul>
                <li>
                    Add your configured Gtalk address as a
                    contact to your Gtalk contact list.
                </li>
                <li>
                    Initiate the conversation by sending something random like "hi"
                </li>
                <li>
                    The menu will return and ask your first question.
                    It is configured to ask questions in batches.
                </li>
            </ul>
        </div>
    </div>
</body>
</html>""" % self.config)
        request.finish()
        return NOT_DONE_YET

class PollResource(Resource):

    def __init__(self, poll_manager, results_manager, config):
        Resource.__init__(self)
        path_prefix = config['path']
        request_path_bits = filter(None, path_prefix.split('/'))

        def create_node(node, path):
            if path in node.children:
                return node.children.get(path)
            else:
                new_node = Resource()
                node.putChild(path, new_node)
                return new_node

        parent = reduce(create_node, request_path_bits, self)
        parent.putChild('results',
            PollResultsResource(poll_manager, results_manager))
        parent.putChild('active',
            PollActiveResource(poll_manager, results_manager))
        parent.putChild('completed',
            PollCompletedResource(poll_manager, results_manager))
        parent.putChild('results.csv',
            PollResultsCSVResource(results_manager))
        parent.putChild('users.csv',
            PollUsersCSVResource(results_manager))
        parent.putChild('index.html',
            InstructionsResource(config))

class PollDashboardServer(Service):
    def __init__(self, poll_manager, results_manager, config):
        self.webserver = None
        self.port = config['port']
        self.site_factory = Site(PollResource(poll_manager, results_manager,
            config))

    @inlineCallbacks
    def startService(self):
        self.webserver = yield reactor.listenTCP(self.port,
                                                 self.site_factory)

    @inlineCallbacks
    def stopService(self):
        if self.webserver is not None:
            yield self.webserver.loseConnection()
