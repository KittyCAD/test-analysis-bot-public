# Features

## Results

When a test is first introduced on a branch, later uploads for the same commit
do not override the original outcome. The API keeps reporting that first result
(including whether it should block the PR), so a flaky retry that passes cannot
turn the status green. In the UI, those failures show an “added this broken
test” badge and do not offer a rerun control.
