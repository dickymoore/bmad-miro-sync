# Windows Browser Loop

This document is kept only as historical context.

It is no longer the recommended path.

The working setup for this repo is documented in [docs/browser-automation-runbook.md](/home/codexuser/bmad-miro-sync/docs/browser-automation-runbook.md).

## Why this path was retired

The Windows relay approach depended on:

- Windows Chrome CDP exposure
- a WSL-to-Windows bridge
- no-admin firewall workarounds
- a second operational profile boundary

That made it strictly more fragile than the final working approach:

- visible Chromium launched from WSL
- CDP on `127.0.0.1:9222`
- Playwright MCP attached locally in the same namespace

Use this file only if you need to reconstruct the abandoned experiment. For normal operation, ignore it.
