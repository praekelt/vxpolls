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
            f.clean(['equal', 'a', 'b'])
            )

    def test_check_widget_rendering(self):
        f = CheckField(choices=default_choices, help_text='value of')
        widget = f.widget
        self.assertTrue('"equal" selected="selected"' in
                            widget.render('name', ['equal', 'a', 'b']))
        self.assertEqual(f.help_text, 'value of')

    def test_check_field_data(self):
        qf = QuestionForm({
            'checks_0_0': 'equal',
            'checks_0_1': 'a',
            'checks_0_2': 'b',
            })
        self.assertTrue(qf.is_valid())
        self.assertEqual(qf.cleaned_data['checks'][0], ['equal', 'a', 'b'])
