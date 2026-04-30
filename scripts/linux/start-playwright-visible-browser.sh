#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${HOME}/.cache/playwright-visible-profile"
CHROME_BIN="${HOME}/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"

mkdir -p "${PROFILE_DIR}"

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

exec "${CHROME_BIN}" \
  --no-sandbox \
  --remote-debugging-port=9222 \
  --remote-debugging-address=127.0.0.1 \
  --user-data-dir="${PROFILE_DIR}" \
  about:blank
