#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${HOME}/.cache/playwright-visible-profile"
CHROME_BIN="${HOME}/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
START_URL="${PLAYWRIGHT_VISIBLE_BROWSER_URL:-about:blank}"

mkdir -p "${PROFILE_DIR}"

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

exec "${CHROME_BIN}" \
  --no-sandbox \
  --headless=new \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-features=UseSkiaRenderer,Vulkan \
  --disable-background-networking \
  --disable-component-update \
  --disable-sync \
  --no-first-run \
  --no-default-browser-check \
  --remote-debugging-port=9222 \
  --remote-debugging-address=127.0.0.1 \
  --user-data-dir="${PROFILE_DIR}" \
  "${START_URL}"
