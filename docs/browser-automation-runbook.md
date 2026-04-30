# Browser Automation Runbook

This is the stable live-board automation path for `bmad-miro-sync`.

## Final Working Architecture

Use a visible Chromium instance launched from WSL with Chrome DevTools Protocol enabled on `127.0.0.1:9222`, then attach Playwright MCP to that browser with `--cdp-endpoint`.

This keeps all of the moving parts in the same Linux/WSL network namespace while still giving you a visible desktop browser via WSLg.

## Preconditions

1. WSL HTTPS trust is working.
If your environment uses Zscaler or another TLS interception layer, fix the Linux trust store first. Do not rely on `--ignore-certificate-errors` for the normal workflow.

2. The visible Chromium binary exists at:
`/home/codexuser/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`

3. Codex config includes:

```toml
[mcp_servers.playwright]
command = "npx"
args = [
  "@playwright/mcp@latest",
  "--cdp-endpoint",
  "http://127.0.0.1:9222",
  "--ignore-https-errors",
]
```

## Start the Visible Browser

From WSL:

```bash
cd /home/codexuser/bmad-miro-sync
./scripts/linux/start-playwright-visible-browser.sh
```

This launches a visible Chromium window with:

- remote debugging on `127.0.0.1:9222`
- a persistent profile under `~/.cache/playwright-visible-profile`
- no Windows firewall or cross-host relay dependencies

## First-Time Login

In the visible Chromium window:

1. log into Miro
2. open the target board
3. keep that browser running

That login state persists in the visible browser profile.

## Attach Codex

After the visible browser is up:

1. restart Codex
2. confirm Playwright MCP is available
3. confirm the board tab is visible through the browser tools

At that point the agent can:

- navigate the live board
- refresh after publish
- inspect the board visually
- take screenshots
- iterate on layout without manual refresh work

## Recommended Publish Loop

For renderer iteration, do not use full-board publish by default. Use source-scoped publish to avoid Miro WAF failures and to keep turnaround fast.

Recommended loop:

1. clear the board
2. clear local `.bmad-miro-sync/`
3. regenerate the publish plan
4. publish one source artifact, usually:
   - `--source "_bmad-output/planning-artifacts/prd.md"`
5. inspect the board in Playwright
6. patch the renderer
7. repeat

Useful commands:

```bash
PYTHONPATH=/home/codexuser/bmad-miro-sync/src python3 -m bmad_miro_sync run-codex-collaboration-workflow \
  --project-root /home/codexuser/fluidscan \
  --config /home/codexuser/fluidscan/.bmad-miro.toml \
  --runtime-dir /home/codexuser/fluidscan/.bmad-miro-sync/run \
  --stop-after publish
```

```bash
PYTHONPATH=/home/codexuser/bmad-miro-sync/src python3 -m bmad_miro_sync publish-direct \
  --project-root /home/codexuser/fluidscan \
  --config /home/codexuser/fluidscan/.bmad-miro.toml \
  --plan /home/codexuser/fluidscan/.bmad-miro-sync/run/plan.json \
  --results /home/codexuser/fluidscan/.bmad-miro-sync/run/results-prd.json \
  --source "_bmad-output/planning-artifacts/prd.md" \
  --apply-results
```

## Troubleshooting

If the browser opens but HTTPS fails:

- the usual cause is missing Linux trust for Zscaler or another corporate CA
- fix the Linux trust store first

If Codex cannot see Playwright MCP:

- verify the Codex config file in the active `CODEX_HOME`
- restart Codex after config changes

If Miro returns `403` WAF blocks:

- do not keep hammering full-board bulk publishes
- switch to `--source` or `--changed-only`
- sanitize or trim hostile/raw HTML payloads

## Deprecated Approaches

Do not start with these unless the final WSL-local CDP path is impossible:

- Windows Chrome + firewall/relay bridging
- Playwright browser extension mode across Windows/WSL profile boundaries
- hidden Playwright-launched Linux Chromium without CDP attachment
