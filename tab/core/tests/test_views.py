import pytest

from ..constants import TEST_OTP
from ..models import Organization


def describe_login_and_verify():
    login_url = "/accounts/login/"
    verify_url = "/accounts/verify/"

    @pytest.fixture
    def organization():
        return Organization.objects.create(email_domain="example.com")

    @pytest.mark.django_db
    def it_accepts_valid_otp(expect, client, organization):
        # Submit email to login
        response = client.post(login_url, {"email": "test@example.com"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Verify One-Time Password")

        # Submit OTP to verify
        response = client.post(verify_url, {"otp": TEST_OTP}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Logout")

    @pytest.mark.django_db
    def it_rejects_invalid_otp(expect, client, organization):
        # Submit email to login
        response = client.post(login_url, {"email": "test@example.com"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Verify One-Time Password")

        # Submit invalid OTP to verify
        response = client.post(verify_url, {"otp": "invalid"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Invalid OTP. Please try again.")

    @pytest.mark.django_db
    def it_rejects_unknown_domains(expect, client):
        response = client.post(login_url, {"email": "test@example.com"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("No organization found for that email domain.")

    @pytest.mark.django_db
    def it_redirects_to_login_if_no_email_in_session(expect, client):
        # Try to access verify page without going through login first
        response = client.get(verify_url, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Please enter your email address first.")

    @pytest.mark.django_db
    def it_preserves_next_parameter_through_login_flow(expect, client, organization):
        # Submit email to login with next parameter
        response = client.post(
            f"{login_url}?next=/projects/", {"email": "test@example.com"}, follow=True
        )
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Verify One-Time Password")

        # Submit OTP to verify - next parameter should be in the URL
        response = client.post(
            f"{verify_url}?next=/projects/", {"otp": TEST_OTP}, follow=True
        )
        expect(response.status_code) == 200

        # Should redirect to the next URL after successful login
        expect(response.redirect_chain[-1][0]).contains("/projects/")
