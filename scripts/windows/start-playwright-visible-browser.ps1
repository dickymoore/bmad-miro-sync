$ErrorActionPreference = "Stop"

$chromePaths = @(
  "$Env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "$Env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
)

$chromePath = $chromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chromePath) {
  throw "Google Chrome not found in standard install locations."
}

$profileDir = Join-Path $Env:LOCALAPPDATA "playwright-mcp-profile"

Write-Host "Starting visible Chrome for Playwright MCP..."
Write-Host "Chrome: $chromePath"
Write-Host "Profile: $profileDir"
Write-Host "CDP: http://127.0.0.1:9222"

Start-Process -FilePath $chromePath -ArgumentList @(
  "--remote-debugging-port=9222",
  "--remote-debugging-address=127.0.0.1",
  "--user-data-dir=$profileDir"
)
