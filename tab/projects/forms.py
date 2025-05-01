from django import forms

from .models import Test


class BulkUpdateDisabledTestsForm(forms.Form):
    test_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
    disabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Keep selected tests disabled to prevent from blocking merges",
        initial=True,
    )
    disabled_reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Reason Disabled",
        help_text=Test._meta.get_field("disabled_reason").help_text,
    )
    disabled_tracker = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Tracker",
        help_text=Test._meta.get_field("disabled_tracker").help_text,
    )
