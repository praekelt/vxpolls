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
        'checks': {},
    }
    defaults.update(question_dict)
    if not defaults['label']:
        defaults['label'] = defaults['copy']
    if isinstance(defaults['valid_responses'], list):
        list_values = map(unicode, defaults['valid_responses'])
        defaults['valid_responses'] = ', '.join(list_values)
    return defaults

def _normalize_value(key, value):

    def handle_checks(value):
        equality_checks = value.get('equal', {}).items()
        if equality_checks:
            return equality_checks[0]
        else:
            return '', ''

    key_map = {
        'checks': handle_checks
    }
    cb = key_map.get(key, lambda value: value)
    return cb(value)

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
            value = _normalize_value(key, value)
            result['question__%s__%s' % (idx, key)] = value
    return result

def _field_for(key):
    """
    Each key can be assigned a custom field type.
    Defaults to a CharField
    """
    try:
        [_, key_number, key_type] = key.split('__')
    except ValueError:
        key_type = key
        key_number = None

    key_map = {
        'batch_size': forms.IntegerField(required=False),
        'valid_responses': fields.CSVField(
            label='Question %s valid responses' % (key_number,),
            help_text='Only comma separated values are allowed.',
            required=False),
        'copy': forms.CharField(
            label='Question %s text' % (key_number,),
            required=True, widget=forms.Textarea),
        'label': forms.CharField(
            label='Question %s is stored as' % (key_number,),
            required=True),
        'checks': fields.CheckField(
            label='Question %s should only be asked if' % (key_number,),
            required=False),
    }
    return key_map.get(key_type, forms.CharField(required=False))

class VxpollForm(forms.BaseForm):

    def __init__(self, **kwargs):
        data = kwargs.get('initial', {}).copy()
        questions = _roll_up_questions(data.pop('questions', []))
        data.update(questions)
        super(VxpollForm, self).__init__(**kwargs)

    def export(self):
        if not self.is_valid():
            raise ValidationError('form must validate')
        data = {
            'transport_name': self.cleaned_data['transport_name'],
            'poll_id': self.cleaned_data['poll_id'],
            'batch_size': self.cleaned_data['batch_size'],
            'questions': self._export_questions()
        }
        return data

    def _export_questions(self):
        questions = [(key, value) for key, value in self.cleaned_data.items()
                        if key.startswith('question')]
        sample_question = _normalize_question({})
        num_of_parts_per_question = len(sample_question)
        keys_per_question = sample_question.keys()
        total_num_questions = len(questions) / num_of_parts_per_question
        results = []
        for index in range(total_num_questions):
            question = {}
            for key in keys_per_question:
                data_key = 'question__%s__%s' % (index, key)
                question[key] = self.cleaned_data[data_key]
            results.append(question)
        return results


def make_form_class(config_data, base_class):
    """
    Dynamically create a form class for the given configuration
    data. Automatically creates all the necessary fields
    """
    base_fields = SortedDict([
        (key, _field_for(key)) for key in sorted(config_data.keys())
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
    questions = _roll_up_questions(config_data.pop('questions', []))
    config_data.update(questions)
    form_class = make_form_class(config_data, base_class=base_class)

    form_data = kwargs.pop('data', {})
    questions = _roll_up_questions(form_data.pop('questions', []))
    form_data.update(questions)
    return form_class(data=form_data, initial=config_data, **kwargs)
