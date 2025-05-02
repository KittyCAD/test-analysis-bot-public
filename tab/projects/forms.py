from django import forms

from .models import Test


class BaseUpdateTestForm(forms.Form):
    disabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        initial=True,
    )
    disabled_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        label="Disabled Reason",
        help_text=Test._meta.get_field("disabled_reason").help_text,
    )
    disabled_tracker = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Tracker Link",
        help_text=Test._meta.get_field("disabled_tracker").help_text,
    )
    disabled_user = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        required=True,
        label="Your Email",
        help_text="Person who last updated this override behavior",
    )


class BulkUpdateTestForm(BaseUpdateTestForm):
    test_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
    disabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Keep selected tests disabled to prevent from blocking merges",
        initial=True,
    )


class UpdateTestForm(BaseUpdateTestForm):
    test_id = forms.CharField(widget=forms.HiddenInput(), required=True)
    disabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Disable test to prevent from blocking merges",
        initial=True,
    )
