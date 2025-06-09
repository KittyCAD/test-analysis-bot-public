import pytest

from ..constants import TEST_OTP


def describe_login():
    url = "/login/"

    @pytest.mark.django_db
    def it_accepts_valid_otp(expect, client):
        response = client.post(url, {"email": "test@example.com"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Verify One-Time Password")

        response = client.post(
            url, {"email": "test@example.com", "otp": TEST_OTP}, follow=True
        )
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Logout")

    @pytest.mark.django_db
    def it_rejects_invalid_otp(expect, client):
        response = client.post(url, {"email": "test@example.com"}, follow=True)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Verify One-Time Password")

        response = client.post(
            url, {"email": "other@example.com", "otp": TEST_OTP}, follow=True
        )
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("Invalid OTP. Please try again.")
