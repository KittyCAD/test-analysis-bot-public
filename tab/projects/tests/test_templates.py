from ..templatetags.formatting_tags import highlight


def describe_highlight(expect):

    def with_empty_string():
        result = highlight("")
        expect(result) == ""

    def with_regular_line():
        text = "This is a regular line"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def with_plus():
        text = "+added line"
        result = highlight(text)
        expect(result).contains("success")

    def with_minus():
        text = "-removed line"
        result = highlight(text)
        expect(result).contains("danger")

    def with_received():
        text = "Received: some value"
        result = highlight(text)
        expect(result).contains("success")

    def with_expected():
        text = "Expected: some value"
        result = highlight(text)
        expect(result).contains("danger")

    def with_expected_and_timeout():
        text = "Expected: visible\nTimeout: 5000ms"
        result = highlight(text)
        expect(result).contains("danger")
        expect(result).contains("success")

    def with_expected_received_then_timeout():
        text = "Expected: visible\nReceived: hidden\nTimeout: 5000ms"
        result = highlight(text)
        expect(result).contains("danger")  # Expected
        expect(result).contains("success")  # Received
        expect(result.count("text-success")) == 1  # only Received, not Timeout

    def with_playwright_substring():
        text = (
            "Locator: getByTestId('units-menu')\n"
            'Expected substring: "yd"\n'
            'Received string:    "Default units for current file mm"\n'
            "Timeout: 5000ms\n"
        )
        result = highlight(text)
        expect(result.count("text-danger")) == 1
        expect(result.count("text-success")) == 1  # Received only, not Timeout

    def with_timeout_but_no_expected():
        text = "Timeout: 5000ms"
        result = highlight(text)
        expect(result).excludes("success")
        expect(result).excludes("danger")

    def with_dashes_in_logs():
        text = "Call Log:\n- Timeout 5000ms exceeded while waiting on the predicate"
        result = highlight(text)
        expect(result).excludes("text-danger")

    def with_pytest_plus_line():
        text = 'E         +     "/metrics": {'
        result = highlight(text)
        expect(result).contains("success")

    def with_pytest_minus_line():
        text = 'E         -     "/metrics": {'
        result = highlight(text)
        expect(result).contains("danger")

    def with_indented_snapshot_diff_minus():
        """Vitest/Jest snapshot failures indent unified diff lines with spaces."""
        text = (
            "Error: expect(string).toMatchSnapshot(expected) failed\n\n"
            "  @@ -1,8 +1,7 @@\n"
            "   [settings]\n"
            "   modeling = { }\n"
            "  -command_bar = { }\n"
            "\n"
            "  Snapshot: verify-named-view-gets-created.toml\n"
        )
        result = highlight(text)
        expect(result).contains("text-danger")
        expect(result).contains("-command_bar")

    def with_indented_minus_without_hunk_header():
        """Do not treat indented '-…' as diff unless a @@ hunk appeared above."""
        text = "Summary:\n  - bullet item\n  - another\n"
        result = highlight(text)
        expect(result).excludes("text-danger")

    def with_pytest_varying_whitespace():
        text = "E       +\nE   -\nE\t+"
        result = highlight(text)
        expect(result).contains("success")
        expect(result).contains("danger")

    def with_pytest_approx_assertion_failure():
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

    def with_rust_assertion_left_right_failed():
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

    def with_rust_pretty_assertions_diff():
        text = (
            "assertion failed: `(left == right)`\n"
            "\n"
            "Diff < left / right > :\n"
            "<[DEVELOPMENT] Account Deletion Confirmation\n"
            ">Account Deletion Confirmation\n"
            "\n"
            "stack backtrace:\n"
            "   0: __rustc::rust_begin_unwind\n"
        )
        result = highlight(text)
        expect(result).contains("text-danger")
        expect(result).contains("text-success")
        expect(result).contains(
            '<span class="text-danger">&lt;[DEVELOPMENT] Account Deletion Confirmation</span>'
        )
        expect(result).contains(
            '<span class="text-success">&gt;Account Deletion Confirmation</span>'
        )
        expect(result).excludes(
            '<span class="text-success">   0: __rustc::rust_begin_unwind</span>'
        )

    def with_angle_brackets_outside_pretty_diff():
        text = "<not a diff\n>also not a diff\n"
        result = highlight(text)
        expect(result).excludes("text-danger")
        expect(result).excludes("text-success")
