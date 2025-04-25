from django import forms

from .models import Test


class BulkUpdateDisabledTestsForm(forms.Form):
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
    test_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
