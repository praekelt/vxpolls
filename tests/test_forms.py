from django.test import TestCase
from django.core.exceptions import ValidationError

from vxpolls.content.fields import CheckField
from vxpolls.content.forms import QuestionForm


default_choices = [
    ('equal', 'equal'),
    ('not equal', 'not equal'),
    ]


class FormTestCase(TestCase):

    def test_check_field_validation(self):
        f = CheckField(choices=default_choices)

        self.assertRaises(ValidationError, f.clean, ['a', 'b', 'c'])
        self.assertEqual(f.choices, default_choices)
        self.assertEqual(
            ['equal', 'a', 'b'],
            f.clean(['a', 'equal', 'b'])
            )

    def test_check_widget_rendering(self):
        f = CheckField(choices=default_choices, help_text='value of')
        widget = f.widget
        self.assertTrue('"equal" selected="selected"' in
                            widget.render('name', ['a', 'equal', 'b']))
        self.assertEqual(f.help_text, 'value of')

    def test_check_field_data(self):
        qf = QuestionForm({
            'check_0': 'a',
            'check_1': 'equal',
            'check_2': 'b',
            })
        qf.is_valid()
        self.assertTrue(qf.is_valid())
        self.assertEqual(qf.cleaned_data['check'], ['equal', 'a', 'b'])
