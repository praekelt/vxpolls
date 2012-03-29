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


class CheckWidget(forms.Widget):

    def render(self, name, value, attrs):
        check_field, check_value = value

        defaults = {
            'type': 'text',
        }
        field_attrs = defaults.copy()
        field_attrs.update({
            'name': 'field',
            'value': check_field,
        })
        value_attrs = defaults.copy()
        value_attrs.update({
            'name': 'value',
            'value': check_value,
        })

        return mark_safe(u''.join([
            u'<input %s/>' % (flatatt(field_attrs),),
            u' must equal ',
            u'<input %s/>' % (flatatt(value_attrs),),
        ]))

class CheckField(forms.Field):

    widget = CheckWidget

    def to_python(self, value):
        if value == ('', ''):
            return {}
        return {
            'equal': {
                value[0]: value[1]
            }
        }
