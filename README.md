# Test Analysis Bot (TAB)

## Authentik authentication

TAB accepts OpenID Connect logins from the `test-analysis-bot` provider on the
Zoo Corp Authentik instance. Configure the Authentik application with:

- provider type: OAuth2/OpenID Connect
- confidential client and application slug: `test-analysis-bot`
- per-provider issuer mode and an RS256 signing key
- subject mode based on an immutable Authentik user ID or UUID, not email or username
- strict redirect URI: `https://test-analysis-bot.corp.zoo.dev/oidc/callback/`
- authorization code grant and the `openid` and `email` scopes
- an email scope mapping that returns `email_verified: true` only for a
  directory-verified address that the user cannot edit
- an application binding or policy that limits access to the intended users or groups

Write the generated credentials to the Vault KV v2 secret
`secret/corp/test-analysis-bot/authentik_oauth` with `client_id` and
`client_secret` properties. The Kubernetes ExternalSecret maps those properties
to the environment variables expected by Django. Create this Vault secret before
deploying the manifest. For credential rotation, wait for the
`authentik-oauth` ExternalSecret to report `Ready` and verify that the generated
Secret's resource version changed before restarting the deployment. Existing
OIDC sessions are silently reauthorized with Authentik every 15 minutes, so
removing an application binding or disabling an Authentik user takes effect
within that window.

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
        TAB_API_URL: ${{ vars.TAB_API_URL }}
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
      run: |
        cargo nextest run --profile=ci || true  # let TAB determine failure
        .github/workflows/lib/upload-results.sh
      env:
        TAB_API_URL: ${{ vars.TAB_API_URL }}
        TAB_API_KEY: ${{ secrets.TAB_API_KEY }}
        CI_COMMIT_SHA: ${{ github.event.pull_request.head.sha }}
        CI_PR_NUMBER: ${{ github.event.pull_request.number }}
```

and configure the JUnit XML reporter in your `nextest.toml` file:

```toml
[profile.ci.junit]
path = "./test-results/junit.xml"
```
