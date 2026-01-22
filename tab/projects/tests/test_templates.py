from ..templatetags.formatting_tags import highlight


def describe_highlight():

    def returns_empty_string_for_empty_string(expect):
        result = highlight("")
        expect(result) == ""

    def does_not_highlight_regular_lines(expect):
        text = "This is a regular line"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def highlights_addition_lines_with_plus(expect):
        text = "+added line"
        result = highlight(text)
        expect(result).contains("success")

    def highlights_deletion_lines_with_minus(expect):
        text = "-removed line"
        result = highlight(text)
        expect(result).contains("danger")

    def highlights_received_lines(expect):
        text = "Received: some value"
        result = highlight(text)
        expect(result).contains("success")

    def highlights_expected_lines(expect):
        text = "Expected: some value"
        result = highlight(text)
        expect(result).contains("danger")

    def highlights_pytest_error_lines_with_plus(expect):
        text = 'E         +     "/metrics": {'
        result = highlight(text)
        expect(result).contains("success")

    def highlights_pytest_error_lines_with_minus(expect):
        text = 'E         -     "/metrics": {'
        result = highlight(text)
        expect(result).contains("danger")

    def highlights_pytest_error_lines_with_varying_whitespace(expect):
        text = "E       +\nE   -\nE\t+"
        result = highlight(text)
        expect(result).contains("success")
        expect(result).contains("danger")
