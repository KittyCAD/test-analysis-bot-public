import pytest

from ..types import Message


def describe_message():
    @pytest.fixture
    def message():
        return Message(
            text="Failures increased by 10% today",
            label="my project › my test",
            url="https://example.com",
        )

    def it_formats_as_text(expect, message: Message):
        expect(str(message)) == (
            "Failures increased by 10% today: my project › my test"
        )

    def it_formats_as_html(expect, message: Message):
        expect(message.html) == (
            "Failures increased by 10% today: "
            "<a href='https://example.com' target='_blank'>my project › my test</a>"
        )

    def it_formats_as_markdown(expect, message: Message):
        expect(message.markdown) == (
            "Failures increased by 10% today: [my project › my test](https://example.com)"
        )

    def it_formats_as_mrkdwn(expect, message: Message):
        expect(message.mrkdwn) == (
            "Failures increased by 10% today: <https://example.com|my project › my test>"
        )

    def it_formats_as_mrkdwn_with_test_prefix(expect, message: Message):
        message.test = True
        expect(message.mrkdwn) == (
            "`SAMPLE ALERT` Failures increased by 10% today: <https://example.com|my project › my test>"
        )
