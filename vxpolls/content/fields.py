from django import forms
from django.utils.safestring import mark_safe


class CSVWidget(forms.Textarea):

    def render(self, name, value, attrs=None):
        if isinstance(value, list):
            value = ', '.join(value)
        return super(CSVWidget, self).render(name, value, attrs)


class CSVField(forms.Field):

    widget = CSVWidget(attrs={'class': 'span1'})

    def to_python(self, value):
        "Normalize data to a list of strings."
        # Return an empty list if no input was given.
        if not value:
            return []
        return [v.strip() for v in value.split(',')]


class CheckWidget(forms.MultiWidget):

    def __init__(self, attrs=None):
        widgets = (forms.TextInput(attrs=attrs),
                    forms.Select(attrs=attrs),
                    forms.TextInput(attrs=attrs))
        super(CheckWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
            return ('', '', '')
        if isinstance(value, list) and len(value) == 3:
            check_type, field_name, check_value = value
            return [check_type, field_name, check_value]
        return self.backwards_compatible_decompress(value)

    def backwards_compatible_decompress(self, value):
        # This was the braindead old implementation
        equal = value.get('equal', {})
        if equal.items():
            [(label, value)] = equal.items()
            return (label, 'equal', value)
        else:
            return ('', '', '')


class CheckField(forms.MultiValueField):

    widget = CheckWidget(attrs={'class': 'span1'})

    def __init__(self, choices=None, **kwargs):
        self.choices = choices
        fields = (
            forms.CharField(),
            forms.ChoiceField(choices=choices),
            forms.CharField(),
        )
        super(CheckField, self).__init__(fields, **kwargs)
        # Make sure the available choices are set in the widget
        self.widget.widgets[1].choices = choices

    def compress(self, data_list):
        """
        values are displayed as HTML widgets as follows:
          [ ... name ... ] [ check_type select ] [ ... value ... ]
        but are stored as:
          ['check_type', 'name', 'value']
        as a list of Strings in YAML.

        This method makes sure the values are compressed in the right order.
        """
        return [
            data_list[1],  # check type
            data_list[0],  # name
            data_list[2],  # value checked against
        ]
