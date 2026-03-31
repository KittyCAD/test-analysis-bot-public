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

    def with_playwright_substring(expect):
        text = (
            "Locator: getByTestId('units-menu')\n"
            'Expected substring: "yd"\n'
            'Received string:    "Default units for current file mm"\n'
            "Timeout: 5000ms\n"
        )
        result = highlight(text)
        expect(result.count("text-danger")) == 1
        expect(result.count("text-success")) == 1  # Received only, not Timeout

    def with_timeout_but_no_expected(expect):
        text = "Timeout: 5000ms"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def with_dashes_in_logs(expect):
        text = "Call Log:\n- Timeout 5000ms exceeded while waiting on the predicate"
        result = highlight(text)
        expect(result).excludes("text-danger")

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

    def with_pytest_approx_assertion_failure(expect):
        text = (
            "E           assert response.get_volume() == pytest.approx(\n"
            "E                8.295468715405207, rel=0, abs=1e-5\n"
            "E            )\n"
            "E           assert 16.100358703139904 == 8.295468715405207 ± 1.0e-05\n"
            "E             \n"
            "E             comparison failed\n"
            "E             Obtained: 16.100358703139904\n"
            "E             Expected: 8.295468715405207 ± 1.0e-05\n"
        )
        result = highlight(text)
        expect(result).contains("success")  # Obtained
        expect(result).contains("danger")  # Expected
        expect(result).contains("Obtained: 16.100358703139904")
        expect(result).contains("Expected: 8.295468715405207 ± 1.0e-05")

    def with_rust_assertion_left_right_failed(expect):
        text = (
            "assertion `left == right` failed\n"
            '  left: "expected"\n'
            ' right: "actual"\n'
        )
        result = highlight(text)
        expect(result).contains("text-danger")
        expect(result).contains("text-success")
        expect(result).contains("left:")
        expect(result).contains("right:")
