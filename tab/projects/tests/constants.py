TEST_PROMPT = """
The following is exported from the Test Analysis Bot.
Use it to help reproduce, debug, or fix the failure.
Ask the user for approval before running any commands (for example tests, installs, or builds).

## Summary

- **Test:** my-test
- **Project:** foo/bar
- **Status:** Failed
- **Duration:** 12.3s
- **Final retry:** yes
- **Branch:** feature/x
- **Commit:** deadbeef
- **Target:** —
- **Platform:** —
- **Markers:** disabled
- **Failure rate:** 33.3%
  _Total failure rate on significant branches including reruns_
- **Block rate:** 50.0%
  _Effective failure rate with reruns and ignored failures excluded_

## Manual disablement

This test is turned off in the Test Analysis Bot so it does not block merges while the disablement is active (separate from per-run markers).

- **Since:** 2024-06-01T12:00:00+00:00
- **Tracker:** https://example.com/ticket/1

```text
Waiting on infra.
```

## Links

- **Branch:** https://github.com/foo/bar/tree/feature/x
- **Commit:** https://github.com/foo/bar/commit/deadbeef
- **Run:** https://github.com/foo/bar/actions/runs/99

## Message

```text
AssertionError: expected 1 == 2
```

## Additional logs

```json
[
  {
    "step": "build",
    "rc": 1
  }
]
```
""".lstrip()
