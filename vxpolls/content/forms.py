from pprint import pprint
from django import forms
from django.utils.datastructures import SortedDict
from django.core.exceptions import ValidationError
from vxpolls.content import fields


def _normalize_question(question_dict):
    """
    make sure all the keys for a question are present in
    the dictionary when returned
    """
    defaults = {
        'copy': '',
        'label': '',
        'valid_responses': '',
        'checks': {
            'equal': {
                '': '',
            }
        },
    }
    defaults.update(question_dict)
    if not defaults['label']:
        defaults['label'] = defaults['copy']
    if isinstance(defaults['valid_responses'], list):
        list_values = map(unicode, defaults['valid_responses'])
        defaults['valid_responses'] = ', '.join(list_values)
    return defaults

def _roll_up_questions(questions):
    """
    Roll up the question to a flattened dictionary instead
    of a normalized one generating unique keys for each nested
    question.
    """
    result = {}
    questions = questions[:]
    for idx, question in enumerate(questions):
        for key, value in _normalize_question(question).items():
            if key == 'checks':
                equal = value.get('equal', {})
                if equal:
                    key, value = equal.items()[0]
                    result['question--%s--checks_0' % (idx,)] = key
                    result['question--%s--checks_1' % (idx,)] = value
            else:
                result['question--%s--%s' % (idx, key)] = value
    return result

def _field_for(key):
    """
    Each key can be assigned a custom field type.
    Defaults to a CharField
    """
    try:
        [_, key_number, key_type] = key.split('--')
    except ValueError:
        key_type = key
        key_number = None

    key_map = {
        'character_limit': forms.CharField(required=False,
            widget=forms.HiddenInput),
        'dashboard_port': forms.CharField(required=False,
            widget=forms.HiddenInput),
        'dashboard_path_prefix': forms.CharField(required=False,
            widget=forms.HiddenInput),
        'interval': forms.IntegerField(required=False,
            widget=forms.HiddenInput),
        'batch_size': forms.IntegerField(required=False,
            widget=forms.HiddenInput),
        'valid_responses': fields.CSVField(
            label='Question %s valid responses' % (key_number,),
            help_text='Only comma separated values are allowed.',
            required=False),
        'copy': forms.CharField(
            label='Question %s text' % (key_number,),
            help_text='The actual copy that is sent to the phone.',
            required=False, widget=forms.Textarea),
        'label': forms.CharField(
            label='Question %s is stored as' % (key_number,),
            help_text='What to refer and store this value as in the database.',
            widget=forms.TextInput(attrs={'class': 'txtbox'}),
            required=False),
        'checks': fields.CheckField(
            label='Question %s should only be asked if' % (key_number,),
            help_text='Skip this question unless the value of the given label matches the answer given.',
            required=False),
        'poll_id': forms.CharField(required=True, widget=forms.HiddenInput),
        'transport_name': forms.CharField(required=True, widget=forms.HiddenInput),
        'survey_completed_response': forms.CharField(
            label='All Completed response',
            help_text='The copy that is sent at the end of the session.',
            required=False, widget=forms.Textarea),
        'batch_completed_response': forms.CharField(
            label='Batch Completed response',
            help_text='The copy that is sent at the end of a batch.',
            required=False, widget=forms.Textarea),
    }
    return key_map.get(key_type, forms.CharField(required=False))

class VxpollForm(forms.BaseForm):

    def export(self):
        if not self.is_valid():
            raise ValidationError('form must validate')
        data = {
            'transport_name': self.cleaned_data['transport_name'],
            'poll_id': self.cleaned_data['poll_id'],
            'batch_size': self.cleaned_data.get('batch_size', None),
            'questions': self._export_questions()
        }
        return data

    def _export_questions(self):
        questions = [key for key in self.base_fields.keys()
                        if key.startswith('question')]
        sample_question = _normalize_question({})
        keys_per_question = sample_question.keys()
        total_num_questions = max([int(key.split('--')[1])
                                    for key in questions]) + 1
        results = []
        pprint(self.cleaned_data)
        for index in range(total_num_questions):
            copy_key = 'question--%s--copy' % (index,)
            if self.cleaned_data.get(copy_key):
                question = {}
                for key in keys_per_question:
                    data_key = 'question--%s--%s' % (index, key)
                    data = self.cleaned_data.get(data_key)
                    if data:
                        question[key] = data
                results.append(question)
            else:
                print 'nothing', copy_key, self.cleaned_data.get(copy_key)
        return results


def make_form_class(config_data, base_class):
    """
    Dynamically create a form class for the given configuration
    data. Automatically creates all the necessary fields
    """
    keys = set([])
    for key in config_data.keys():
        # check for CheckWidget, ends with 0 or 1 and should
        # be collapsed into a single widget with multiple
        # values
        if key.endswith('0') or key.endswith('1'):
            keys.add(key.split('_', 1)[0])
        else:
            keys.add(key)

    def sort_on_key_index(key):
        try:
            parts = key.split('--')
            return '%s%s' % (parts[1], parts[2])
        except IndexError:
            return 0

    base_fields = SortedDict([
        (key, _field_for(key)) for key in sorted(keys, key=sort_on_key_index)
    ])
    return type('DynamicVxpollForm', (base_class,), {
        'base_fields': base_fields,
    })

def make_form(**kwargs):
    """
    Create a form instance for the given configuration data.
    It dynamically generates the form class and then populates it
    with the given data.
    """
    base_class = kwargs.pop('base_class', VxpollForm)

    config_data = kwargs.pop('initial', {})
    initial_questions = config_data.pop('questions', [])
    initial_questions.append(_normalize_question({}))
    questions = _roll_up_questions(initial_questions)
    config_data.update(questions)
    form_class = make_form_class(config_data, base_class=base_class)

    form_data = kwargs.pop('data', {})
    data_questions = form_data.pop('questions', [])
    questions = _roll_up_questions(data_questions)
    form_data.update(questions)
    return form_class(data=form_data, initial=config_data, **kwargs)
