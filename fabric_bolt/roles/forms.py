from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, ButtonHolder, Submit

from fabric_bolt.roles import models


class RoleCreateForm(forms.ModelForm):
    class Meta:
        model = models.Role

    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-lg-2'
    helper.field_class = 'col-lg-8'
    helper.layout = Layout(
        'name',
        ButtonHolder(
            Submit('submit', 'Create Role', css_class='button')
        )
    )


class RoleUpdateForm(RoleCreateForm):

    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-lg-2'
    helper.field_class = 'col-lg-8'
    helper.layout = Layout(
        'name',
        ButtonHolder(
            Submit('submit', 'Update Role', css_class='button')
        )
    )
