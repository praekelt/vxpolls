# -*- test-case-name: tests.test_manager -*-
import time
import json
import hashlib
import csv
from datetime import datetime
from StringIO import StringIO

from twisted.internet.defer import returnValue

from vumi.components.session import SessionManager
from vumi.persist.redis_base import Manager

from vxpolls.participant import PollParticipant
from vxpolls.results import ResultManager


class PollManager(object):
    def __init__(self, r_server, r_prefix='poll_manager'):
        # create a manager attribute so the @calls_manager works
        self.r_server = self.manager = r_server
        self.r_prefix = r_prefix
        self.sr_server = self.r_server.sub_manager(self.r_key())
        self.session_manager = SessionManager(self.sr_server)

    def r_key(self, *args):
        parts = [self.r_prefix]
        parts.extend(args)
        return ':'.join(map(unicode, parts))

    def generate_unique_id(self, version):
        return hashlib.md5(json.dumps(version)).hexdigest()

    def exists(self, poll_id):
        return self.r_server.sismember(self.r_key('polls'), poll_id)

    def polls(self):
        return self.r_server.smembers(self.r_key('polls'))

    @Manager.calls_manager
    def set(self, poll_id, version):
        # NOTE: If two versions of a poll are created within an interval
        # shorter than time.time()'s resolution, they'll both get the same
        # score and we won't know which is newer. This is much less likely now
        # that we take the repr() of the timestamp instead of using implicit
        # string conversion (which rounds/truncates to 10ms precision).
        uid = self.generate_unique_id(version)
        yield self.r_server.sadd(self.r_key('polls'), poll_id)
        yield self.r_server.hset(self.r_key('versions', poll_id), uid,
                                    json.dumps(version))
        key = self.r_key('version_timestamps', poll_id)
        yield self.r_server.zadd(key, **{
            uid: repr(time.time()),
        })
        returnValue(uid)

    @Manager.calls_manager
    def register(self, poll_id, version):
        uid = yield self.set(poll_id, version)
        poll = yield self.get(poll_id, uid=uid)
        returnValue(poll)

    @Manager.calls_manager
    def get_latest_uid(self, poll_id):
        timestamps_key = self.r_key('version_timestamps', poll_id)
        uids = yield self.r_server.zrange(timestamps_key, 0, -1, desc=True)
        if uids:
            returnValue(uids[0])

    def get_session_key(self, poll_id, user_id):
        return '%s-%s' % (poll_id, user_id)

    @Manager.calls_manager
    def get_config(self, poll_id, uid=None):
        if uid is None:
            uid = yield self.get_latest_uid(poll_id)
        if uid:
            versions_key = self.r_key('versions', poll_id)
            json_data = yield self.r_server.hget(versions_key, uid)
            returnValue(json.loads(json_data))

        returnValue({})

    @Manager.calls_manager
    def uid_exists(self, poll_id, uid):
        versions_key = self.r_key('versions', poll_id)
        exists = yield self.r_server.hexists(versions_key, uid)
        returnValue(exists)

    @Manager.calls_manager
    def get(self, poll_id, uid=None):
        if not (yield self.uid_exists(poll_id, uid)):
            uid = yield self.get_latest_uid(poll_id)
        version = yield self.get_config(poll_id, uid)
        if version:
            repeatable = version.get('repeatable', True)
            case_sensitive = version.get('case_sensitive', True)
            poll = yield Poll.mkpoll(
                self.r_server, poll_id, uid, version['questions'],
                version.get('batch_size'), r_prefix=self.r_key('poll'),
                repeatable=repeatable, case_sensitive=case_sensitive)
            returnValue(poll)

    @Manager.calls_manager
    def get_participant(self, poll_id, user_id):
        # TODO
        session_key = self.get_session_key(poll_id, user_id)
        session_data = yield self.session_manager.load_session(session_key)
        participant = PollParticipant(user_id, session_data)
        returnValue(participant)

    def get_poll_for_participant(self, poll_id, participant):
        return self.get(poll_id, participant.get_poll_uid())

    @Manager.calls_manager
    def save_participant(self, poll_id, participant):
        participant.updated_at = time.time()
        session_key = self.get_session_key(poll_id, participant.user_id)
        yield self.session_manager.save_session(session_key,
                                    participant.clean_dump())

    @Manager.calls_manager
    def clone_participant(self, participant, poll_id, new_id):
        participant.updated_at = time.time()
        session_key = self.get_session_key(poll_id, new_id)
        yield self.session_manager.save_session(session_key,
                                    participant.clean_dump())
        clone = yield self.get_participant(poll_id, new_id)
        returnValue(clone)

    @Manager.calls_manager
    def active_participants(self, poll_id):
        active_sessions = yield self.session_manager.active_sessions()
        all_participants = [PollParticipant(session.get('user_id'), session)
                            for session_id, session in active_sessions]
        active_participants = [participant for participant in all_participants
                    if participant.get_poll_id() == poll_id]
        returnValue(active_participants)

    def inactive_participant_session_keys(self):
        archive_key = self.r_key('archive')
        return self.r_server.smembers(archive_key)

    @Manager.calls_manager
    def archive(self, poll_id, participant):
        user_id = participant.user_id
        session_key = self.get_session_key(poll_id, user_id)
        archive_key = self.r_key('archive')
        yield self.r_server.sadd(archive_key, session_key)

        session_archive_key = self.r_key('session_archive', session_key)
        yield self.r_server.zadd(session_archive_key, **{
            json.dumps(participant.clean_dump()): participant.updated_at,
        })
        # TODO
        yield self.session_manager.clear_session(session_key)

    @Manager.calls_manager
    def get_all_archives(self):
        user_ids = yield self.inactive_participant_user_ids()
        archives = []
        for user_id in user_ids:
            archive = yield self.get_archive(user_id)
            archives.append(archive)
        returnValue(archives)

    @Manager.calls_manager
    def get_archive(self, poll_id, user_id):
        session_key = self.get_session_key(poll_id, user_id)
        archive_key = self.r_key('session_archive', session_key)
        archived_sessions = yield self.r_server.zrange(archive_key, 0, -1,
                                                    desc=True)

        # NOTE:
        #
        # other places where we load session data we're loading session data
        # it comes straight from redis as string values from a hash. In the
        # case of archives it is slightly different since they're just stored
        # as JSON blobs, before we hand it over to the PollParticipant we
        # need to make sure all values are again passed in as strings as they
        # would when loaded from Redis.
        archives = []
        for data in archived_sessions:
            typed_json = json.loads(data)
            unicode_json = dict([(key, unicode(value)) for key, value
                                    in typed_json.items()])
            participant = PollParticipant(user_id, unicode_json)
            archives.append(participant)

        returnValue(archives)

    @Manager.calls_manager
    def get_completed_response(self, participant, poll, default_response):
        config = yield self.get_config(poll.poll_id)
        # Get the known survey completed responses (which might not exist)
        # but always tag the default response on the end, since it doesn't
        # have any checks it will always pass and so we're guaranteed
        # to have a response if even whoever wrote the survey description
        # manages to create a situation where all other checks fail.
        possible_responses = config.get('survey_completed_responses', [])
        possible_responses.append({'copy': default_response})
        survey_completed_responses = enumerate(possible_responses)

        for index, response in survey_completed_responses:
            pq = PollQuestion(index, **response)
            if poll.is_suitable_question(participant, pq):
                returnValue(pq.copy)
        returnValue(self.survey_completed_response)

    def stop(self):
        return self.session_manager.stop(stop_redis=False)

    @Manager.calls_manager
    def export_user_data(self, poll, include_timestamp=True,
                         include_old_questions=False):
        """
        Export the user data for a poll, returns
            [(user_id, user_data_dict), ...]

        :param bool include_timestamp:
            If true it inserts a `user_timestamp` key & timestamp value for
            each dict with user data. The timestamp reflects the participants
            `updated_at` value. If `user_timestamp` already exists as a key
            in the user data then it is left as is.

        :param bool include_old_questions:
            If true, responses to questions from older versions of the poll
            are included.
        """
        if include_old_questions:
            questions = None
        else:
            questions = [q['label'] for q in poll.questions]
        users = yield poll.results_manager.get_users(poll.poll_id, questions)
        if not include_timestamp:
            returnValue(users)
        for user_id, user_data in users:
            timestamp = yield self.get_participant_timestamp(poll.poll_id,
                                                                user_id)
            user_data.setdefault('user_timestamp', timestamp)
        returnValue(users)

    @Manager.calls_manager
    def export_user_data_as_csv(self, poll, include_timestamp=True,
                                include_old_questions=False):
        """
        See `export_user_data`

        Returns the user data in UTF-8 encoded CSV format.
        """
        users = yield self.export_user_data(
            poll, include_timestamp=include_timestamp,
            include_old_questions=include_old_questions)
        sio = StringIO()
        field_names = ['user_id']
        if include_timestamp:
            field_names.append('user_timestamp')
        if include_old_questions:
            old_questions = set()
            for user_id, user_data in users:
                old_questions.update(user_data.iterkeys())
            old_questions.discard('user_timestamp')
            field_names.extend(sorted(old_questions))
        else:
            field_names.extend([q['label'].encode('utf-8')
                                for q in poll.questions])
        writer = csv.DictWriter(sio, fieldnames=field_names)
        # write header row
        writer.writerow(dict(zip(field_names, field_names)))
        for user_id, user_data in users:
            row = {'user_id': user_id}
            row.update(user_data)
            writer.writerow(row)
        returnValue(sio.getvalue())

    @Manager.calls_manager
    def get_participant_timestamp(self, poll_id, user_id):
        participant = yield self.get_participant(poll_id, user_id)
        returnValue(datetime.fromtimestamp(participant.updated_at))


class Poll(object):
    def __init__(self, r_server, poll_id, uid, questions, batch_size=None,
        r_prefix='poll', repeatable=True, case_sensitive=True):
        self.r_server = self.manager = r_server
        self.poll_id = poll_id
        self.uid = uid
        self.questions = questions
        self.r_prefix = r_prefix
        self.batch_size = batch_size
        self.repeatable = repeatable
        self.case_sensitive = case_sensitive
        # Result Manager keeps track of what was answered
        # to which question. We need to tell it about the options
        # before hand.
        self.results_manager = ResultManager(self.r_server,
                                                self.r_key('results'))
        self._setup_d = self._setup_results()

    @Manager.calls_manager
    def _setup_results(self):
        yield self.results_manager.register_collection(self.poll_id)
        for index, question_data in enumerate(self.questions):
            question_data = dict((k.encode('utf8'), v)
                                 for k, v in question_data.items())
            question = PollQuestion(index, case_sensitive=self.case_sensitive,
                                    **question_data)
            yield self.results_manager.register_question(self.poll_id,
                question.label_or_copy(), question.valid_responses)
        returnValue(self)

    @classmethod
    def mkpoll(cls, *args, **kw):
        return cls(*args, **kw)._setup_d

    def r_key(self, *args):
        parts = [self.r_prefix]
        parts.extend(args)
        return ':'.join(parts)

    def get_last_question(self, participant):
        index = participant.get_last_question_index()
        if index is not None:
            return self.get_question(index)

    def set_last_question(self, participant, question):
        participant.set_last_question_index(question.index)

    def get_next_question(self, participant, last_index=None):
        if last_index is None:
            last_question = self.get_last_question(participant)
        else:
            last_question = self.get_question(last_index)

        if last_question:
            next_index = last_question.index + 1
        else:
            next_index = 0
        question = self.get_question(next_index)
        if question:
            if self.is_suitable_question(participant, question):
                return question
            else:
                return self.get_next_question(participant, next_index)

    def is_suitable_question(self, participant, question):

        state = participant.labels
        if not self.case_sensitive:
            state = dict((k, v.lower()) for k, v in state.items())

        def equals(key, value):
            return unicode(state.get(key)) == unicode(value)

        def not_equals(key, value):
            return unicode(state.get(key)) != unicode(value)

        def exists(key, value=None):
            return state.get(key)

        def not_exists(key, value=None):
            return not exists(key, value)

        def less(key, value):
            return state.get(key) < unicode(value)

        def less_equal(key, value):
            return state.get(key) <= unicode(value)

        def greater(key, value):
            return state.get(key) > unicode(value)

        def greater_equal(key, value):
            return state.get(key) >= unicode(value)

        operations_dispatcher = {
            'equal': equals,
            'not equal': not_equals,
            'exists': exists,
            'not exists': not_exists,
            'less': less,
            'less or equal': less_equal,
            'greater': greater,
            'greater or equal': greater_equal,
        }

        for operation, key, value in question.checks:
            handler = operations_dispatcher.get(operation, lambda *a: True)
            if key:
                if not self.case_sensitive:
                    value = value.lower()
                if not handler(key, value):
                    return False

        return True

    @Manager.calls_manager
    def submit_answer(self, participant, answer, custom_answer_logic=None):
        poll_question = self.get_last_question(participant)
        assert poll_question, 'Need a question to submit an answer for'
        if answer and poll_question.answer(answer):
            yield self.results_manager.add_result(self.poll_id,
                participant.user_id, poll_question.label_or_copy(), answer)
            if poll_question.label is not None:
                participant.set_label(poll_question.label, answer)
                if custom_answer_logic:
                    yield custom_answer_logic(participant, answer,
                        poll_question)
            participant.interactions += 1
        else:
            returnValue(poll_question.copy)

    def has_more_questions_for(self, participant):
        next_question = self.get_next_question(participant)
        return next_question and participant.has_remaining_interactions()

    def has_question(self, index):
        return self.questions and index < len(self.questions)

    def get_question(self, index):
        if self.has_question(index):
            questions = dict((k.encode('utf8'), v)
                             for k, v in self.questions[index].items())
            return PollQuestion(index, case_sensitive=self.case_sensitive,
                **questions)
        return None


class PollQuestion(object):
    def __init__(self, index, copy, label=None, valid_responses=[],
                    checks=None, case_sensitive=True):
        self.index = index
        self.copy = copy
        self.label = label
        self.valid_responses = [unicode(a) for a in valid_responses]
        # Backwards compatibility, convert dict style to list style
        if isinstance(checks, dict):
            checks = [[operation, params.keys()[0], params.values()[0]]
                        for operation, params in checks.items()]
        self.checks = checks or []
        self.case_sensitive = case_sensitive
        self.answered = False

    def label_or_copy(self):
        return self.label or self.copy

    def answer(self, answer):
        if answer is None:
            return False

        if self.case_sensitive:
            valid_responses, answer = self.valid_responses, answer
        else:
            valid_responses = [r.lower() for r in self.valid_responses]
            answer = answer.lower()

        if valid_responses and (answer not in valid_responses):
            return False
        else:
            self.answer = answer
            self.answered = True
            return self.answered

    def __repr__(self):
        return '<PollQuestion copy: %s, responses: %s>' % (
            repr(self.copy), repr(self.valid_responses))
