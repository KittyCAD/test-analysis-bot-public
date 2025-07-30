# Test Analysis Bot (TAB)

## Examples

### E2E Tests: Playwright + TypeScript + GitHub

To set up a TypeScript-based project using Playwright for end-to-end tests that are run via GitHub Actions, copy [api-reporter.ts](docs/examples/playwright/api-reporter.ts) to `.github/workflows/lib/api-reporter.ts` and reference in your `playwright.config.ts` file:

```typescript
export default defineConfig({
  ...
  reporter: [
    ['./.github/workflows/lib/api-reporter.ts'],
    ...
})
```

then provide the necessary environment variables in your `.github/workflows/e2e.yml` file:

```yaml
jobs:
  test:
    ...
    - run: npm run e2e
      env:
        TAB_API_URL: ${{ secrets.TAB_API_URL }}
        TAB_API_KEY: ${{ secrets.TAB_API_KEY }}
        CI_COMMIT_SHA: ${{ github.event.pull_request.head.sha }}
        CI_PR_NUMBER: ${{ github.event.pull_request.number }}
```

### Unit Tests: Cargo Nextest + GitHub

To set up a Rust-based project using Nextest for unit tests that are run via GitHub Actions, copy [upload-results.sh](docs/examples/junit/upload-results.sh) to `.github/workflows/lib/upload-results.sh` and call that from your `.github/workflows/unit.yml` file:

```yaml
jobs:
  test:
    ...
    - name: Run tests
      run:  |
        cargo nextest run --profile=ci || true  # let TAB determine failure
        .github/workflows/lib/upload-results.sh
      env:
        TAB_API_URL: ${{ secrets.TAB_API_URL }}
        TAB_API_KEY: ${{ secrets.TAB_API_KEY }}
        CI_COMMIT_SHA: ${{ github.event.pull_request.head.sha }}
        CI_PR_NUMBER: ${{ github.event.pull_request.number }}
```

and configure the JUnit XML reporter in your `nextest.toml` file:

```toml
[profile.ci.junit]
path = "./test-results/junit.xml"
```
