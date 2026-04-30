# Browser Automation Lessons Learned

Date: 2026-04-30

## Outcome

The stable browser automation loop for this project is:

- launch a visible Chromium browser from WSL
- enable CDP on `127.0.0.1:9222`
- attach Playwright MCP to that browser with `--cdp-endpoint`
- keep Miro login state in the persistent visible-browser profile

This works with the live board and does not require manual refresh steps once configured.

## What Failed

### 1. Default Playwright MCP browser launch

Problem:
- the MCP-managed browser was effectively headless in this environment
- there was no reliable visible desktop window to inspect interactively

Conclusion:
- not suitable for live visual board iteration

### 2. Windows Chrome + CDP + firewall

Problem:
- Windows Chrome served CDP locally
- WSL could not reliably reach the CDP port without firewall changes
- no-admin environments blocked the clean firewall path

Conclusion:
- technically viable, operationally fragile here

### 3. Playwright extension mode

Problem:
- the extension was installed in Windows Chrome
- the MCP process in WSL looked for extension state in the Linux browser profile
- the profile split made the path non-viable

Conclusion:
- not a good fit for cross-OS browser ownership in this setup

## What Worked

### Visible WSL browser with localhost CDP

Why it worked:
- browser process and Playwright MCP were in the same network namespace
- CDP was reachable on `127.0.0.1:9222`
- WSLg provided a visible browser window
- persistent Linux browser profile preserved Miro login

This removed:
- Windows firewall dependence
- cross-host relay complexity
- browser-profile mismatch

## Miro Publishing Lessons

### 1. Full-board bulk publish is the wrong inner loop

Problem:
- Miro WAF blocks large or suspicious bulk payloads
- full-board publish is slower and harder to diagnose

Working practice:
- iterate with source-scoped publish
- prefer:
  - `--source "_bmad-output/planning-artifacts/prd.md"`
  - or `--changed-only`

### 2. Raw markdown sections produce ugly boards

Problem:
- one-text-item-per-section created unreadable document dumps
- phase scaffolding dominated the viewport

Working fix:
- render document sections as shape-backed summary cards
- lighten phase scaffolding
- use source headers and workstream headers
- cap publish depth to heading level 2 by default

### 3. Miro is a collaboration surface, not the source of truth

Working principle:
- BMAD markdown remains the canonical artifact
- Miro receives summaries and navigable structure
- board fidelity should prioritize readability and collaboration over lossless text replication

## Final Renderer Decisions

1. `doc` items are published as shapes, not text nodes.
2. Card bodies are summary-first, not full markdown dumps.
3. Published heading depth defaults to `publish.max_heading_level = 2`.
4. Workstream/source hierarchy is explicit.
5. Phase zones are visually present but de-emphasized.

## Future Operating Rules

1. Fix WSL certificate trust properly before attempting browser automation.
2. Start the visible browser with `scripts/linux/start-playwright-visible-browser.sh`.
3. Use the Playwright MCP CDP config on `127.0.0.1:9222`.
4. Use source-scoped publishes for iteration.
5. Only use full-board rebuilds deliberately.

## Security Notes

During experimentation, a Playwright extension token was exposed in chat.

Action:
- revoke or rotate that token
- do not rely on extension mode for this workflow going forward
