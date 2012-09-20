from django import forms


class CSVWidget(forms.Textarea):

    def render(self, name, value, attrs=None):
        if isinstance(value, list):
            value = ', '.join(map(unicode, value))
        return super(CSVWidget, self).render(name, value, attrs)


class CSVField(forms.Field):

    widget = CSVWidget

    def to_python(self, value):
        "Normalize data to a list of strings."
        # Return an empty list if no input was given.
        if not value:
            return []
        return [v.strip() for v in value.split(',')]


class CheckWidget(forms.MultiWidget):

    def __init__(self, choices=None, attrs=None):
        widgets = (forms.Select(attrs=attrs, choices=choices),
                    forms.TextInput(attrs=attrs),
                    forms.TextInput(attrs=attrs))
        super(CheckWidget, self).__init__(widgets, attrs)

    def format_output(self, widgets):
        """
        Stuff is stored in the config in the format:

            [`operation`, arg1, arg2, ...]

        in the UI we want it shown as :

            <input arg1> <select operation> <input arg2>

        This is why the widgets 0 & 1 are swapped around when rendered.
        """
        return u' '.join([
            widgets[1],
            widgets[0],
            widgets[2],
            ])

    def decompress(self, value):
        if not value:
            return ('', '', '')
        if isinstance(value, dict):
            return self.backwards_compatible_decompress(value)
        return value

    def backwards_compatible_decompress(self, value):
        # This was the braindead old implementation
        equal = value.get('equal', {})
        if equal.items():
            [(label, value)] = equal.items()
            return ('equal', label, value)
        else:
            return ('', '', '')


class CheckField(forms.MultiValueField):

    def __init__(self, choices=None, **kwargs):
        self.choices = choices
        fields = (
            forms.ChoiceField(choices=self.choices),
            forms.CharField(),
            forms.CharField(),
        )

        self.widget = CheckWidget(choices=self.choices)
        super(CheckField, self).__init__(fields, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return ['', '', '']
        return data_list


class MultiCheckWidget(forms.MultiWidget):

    def __init__(self, amount=2, choices=None, attrs=None):
        self.amount = amount
        widgets = [CheckWidget(attrs=attrs, choices=choices)
                    for i in range(self.amount)]
        super(MultiCheckWidget, self).__init__(widgets, attrs)

    def format_output(self, widgets):
        return '<div>%s</div>' % ('</div><div>'.join(widgets),)

    def decompress(self, value):
        if value is None:
            return [['', '', ''] for i in range(self.amount)]
        # backwards compatibility
        if isinstance(value, dict):
            [(type_check, dict_value)] = value.items()
            [(label, label_value)] = dict_value.items()
            return [[type_check, label, label_value]]
        return value


class MultipleCheckFields(forms.MultiValueField):

    def __init__(self, amount=2, choices=None, **kwargs):
        fields = [CheckField(choices=choices, **kwargs) for i in range(amount)]
        self.widget = MultiCheckWidget(amount=amount, choices=choices,
                                        attrs={'class': 'span1'})
        super(MultipleCheckFields, self).__init__(fields, **kwargs)

    def compress(self, data_list):
        return data_list
