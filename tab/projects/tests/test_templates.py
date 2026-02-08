from ..templatetags.formatting_tags import highlight


def describe_highlight():

    def with_empty_string(expect):
        result = highlight("")
        expect(result) == ""

    def with_regular_line(expect):
        text = "This is a regular line"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def with_plus(expect):
        text = "+added line"
        result = highlight(text)
        expect(result).contains("success")

    def with_minus(expect):
        text = "-removed line"
        result = highlight(text)
        expect(result).contains("danger")

    def with_received(expect):
        text = "Received: some value"
        result = highlight(text)
        expect(result).contains("success")

    def with_expected(expect):
        text = "Expected: some value"
        result = highlight(text)
        expect(result).contains("danger")

    def with_expected_and_timeout(expect):
        text = "Expected: visible\nTimeout: 5000ms"
        result = highlight(text)
        expect(result).contains("danger")
        expect(result).contains("success")

    def with_expected_received_then_timeout(expect):
        text = "Expected: visible\nReceived: hidden\nTimeout: 5000ms"
        result = highlight(text)
        expect(result).contains("danger")  # Expected
        expect(result).contains("success")  # Received
        expect(result.count("text-success")) == 1  # only Received, not Timeout

    def with_timeout_but_no_expected(expect):
        text = "Timeout: 5000ms"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def with_pytest_plus_line(expect):
        text = 'E         +     "/metrics": {'
        result = highlight(text)
        expect(result).contains("success")

    def with_pytest_minus_line(expect):
        text = 'E         -     "/metrics": {'
        result = highlight(text)
        expect(result).contains("danger")

    def with_pytest_varying_whitespace(expect):
        text = "E       +\nE   -\nE\t+"
        result = highlight(text)
        expect(result).contains("success")
        expect(result).contains("danger")
