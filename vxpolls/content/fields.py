from django import forms
from django.forms.util import flatatt
from django.utils.safestring import mark_safe


class CSVField(forms.Field):

    widget = forms.TextInput

    def to_python(self, value):
        "Normalize data to a list of strings."
        # Return an empty list if no input was given.
        if not value:
            return []
        return [v.strip() for v in value.split(',')]


class CheckWidget(forms.MultiWidget):

    def __init__(self, attrs=None):
        widgets = (forms.TextInput(attrs=attrs),
                   forms.TextInput(attrs=attrs))
        super(CheckWidget, self).__init__(widgets, attrs)

    def format_output(self, widgets):
        return mark_safe(u' '.join([
            widgets[0],
            u'equals',
            widgets[1],
        ]))

    def decompress(self, value):
        equal = value.get('equal', {})
        if equal.items():
            return equal.items()[0]
        else:
            return ('', '')


class CheckField(forms.MultiValueField):

    widget = CheckWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.CharField(),
            forms.CharField(),
        )
        super(CheckField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return {
                'equal': {
                    data_list[0]: data_list[1],
                }
            }
        else:
            return {}
