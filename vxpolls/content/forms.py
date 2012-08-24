# -*- test-case-name: tests.test_forms -*-

from django import forms
from django.forms.formsets import formset_factory

from vxpolls.content import fields


class PollForm(forms.Form):
    poll_id = forms.CharField(required=True, widget=forms.HiddenInput)
    repeatable = forms.BooleanField(label='Can contacts interact repeatedly?',
        required=False, initial=True)
    case_sensitive = forms.BooleanField(label='Are the valid responses for '
        'each question case sensitive?', required=False, initial=True)
    include_labels = fields.CSVField(required=False,
        label='Responses to include from previous sessions')
    survey_completed_response = forms.CharField(
            label='Closing copy at survey completion',
            help_text='The copy that is sent at the end of the session.',
            initial='Thanks! You have completed the survey',
            required=False, widget=forms.Textarea)


class QuestionForm(forms.Form):

    copy = forms.CharField(required=False, widget=forms.Textarea)
    checks = fields.MultipleCheckFields(amount=3, choices=[
        ('', 'Please select:'),
        ('equal', 'equals'),
        ('not equal', 'does not equal'),
        ('exists', 'exists'),
        ('not exists', 'does not exist'),
        ('greater', 'greater than'),
        ('less', 'less than'),
        ], label="Question should only be asked if the stored value of:")
    label = forms.CharField(required=False,
        label="The response is stored in the database as:")
    valid_responses = fields.CSVField(required=False,
        label="Valid responses (comma separated)")


def make_form_set(extra=1, **kwargs):
    QuestionFormset = formset_factory(QuestionForm, extra=extra)
    return QuestionFormset(**kwargs)
