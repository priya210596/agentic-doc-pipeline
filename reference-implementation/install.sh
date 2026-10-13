#!/bin/sh
# Sets up everything doc-aidev needs, then runs the tests. Safe to re-run.
#   sh install.sh            full setup (adds screenshot support)
#   sh install.sh --no-browser   core only, skips Playwright and Chromium
cd "$(dirname "$0")"
ok()   { echo "  ok    $1"; }
warn() { echo "  WARN  $1"; }
fail() { echo "  FAIL  $1"; exit 1; }

echo "Checking requirements"
command -v python3 >/dev/null || fail "python3 not found (need 3.9 or newer)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || fail "Python 3.9 or newer is required"
ok "python $(python3 -c 'import platform; print(platform.python_version())')"
command -v git >/dev/null && ok "git" || warn "git not found (needed to read repo history; plain folders still work)"
if command -v gh >/dev/null; then ok "gh (GitHub CLI)"; else warn "gh not found; only the GitHub tracker needs it (https://cli.github.com, then 'gh auth login')"; fi

if [ "$1" != "--no-browser" ]; then
  echo "Installing screenshot support"
  python3 -m pip install --quiet -r requirements.txt || fail "pip could not install Playwright"
  ok "playwright package"
  python3 -m playwright install chromium >/dev/null 2>&1 || fail "could not download Chromium (check network access)"
  ok "chromium browser"
fi

echo "Running tests"
python3 -m unittest discover -s tests 2>&1 | tail -3
echo "Try it: sh examples/rack-manager/run_demo.sh"
