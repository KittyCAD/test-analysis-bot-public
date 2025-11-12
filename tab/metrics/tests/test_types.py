import pytest

from ..types import Message


def describe_message():
    @pytest.fixture
    def message():
        return Message(
            text="Failures increased by 10% today",
            label="my_namespace::my project › my test -> my case",
            url="https://example.com",
        )

    def it_formats_as_text(expect, message: Message):
        expect(str(message)) == (
            "Failures increased by 10% today: my_namespace::my project › my test -> my case"
        )

    def it_formats_as_html(expect, message: Message):
        expect(message.html) == (
            "Failures increased by 10% today: "
            "<a href='https://example.com' target='_blank'>my_namespace::my project › my test -> my case</a>"
        )

    def it_formats_as_markdown(expect, message: Message):
        expect(message.markdown) == (
            "Failures increased by 10% today: [my_namespace::my project › my test -> my case](https://example.com)"
        )

    def it_formats_as_mrkdwn(expect, message: Message):
        expect(message.mrkdwn) == (
            "Failures increased by 10% today: <https://example.com|my_namespace:​:my project › my test → my case>"
        )

    def it_formats_as_mrkdwn_with_test_prefix(expect, message: Message):
        message.debug = True
        expect(message.mrkdwn) == (
            "`SAMPLE ALERT` Failures increased by 10% today: <https://example.com|my_namespace:​:my project › my test → my case>"
        )

    def it_truncates_extra(expect, message: Message):
        message.extra = "\n".join(
            [
                "1 " + "x" * 99,
                "2 xxxxxxxxxxx",
                "3 xxxxxxxxxxx",
                "4 xxxxxxxxxxx",
                "5 xxxxxxxxxxx",
                "6 xxxxxxxxxxx",
            ]
        )
        expect(message.markdown).contains(
            "\n".join(
                [
                    "1 " + "x" * 97 + "…",
                    "2 xxxxxxxxxxx",
                    "3 xxxxxxxxxxx",
                    "4 xxxxxxxxxxx",
                    "5 xxxxxxxxxxx",
                    "(1 more line omitted)",
                ]
            )
        )

    def it_truncates_extra_with_short_last_line(expect, message: Message):
        message.extra = "\n".join(
            [
                "1 xxxxxxxxx",
                "2 xxxxxxxxx",
                "3 xxxxxxxxx",
                "4 xxxxxxxxx",
                "Log:",
                "6",
                "7",
            ]
        )
        expect(message.markdown).contains(
            "\n".join(
                [
                    "1 xxxxxxxxx",
                    "2 xxxxxxxxx",
                    "3 xxxxxxxxx",
                    "4 xxxxxxxxx",
                    "(3 more lines omitted)",
                ]
            )
        )
