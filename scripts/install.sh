#!/usr/bin/env bash
# HangarLLM Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/valteresj2/HangarLLM/main/scripts/install.sh | sh
#
# Needs only curl: uv is bootstrapped if missing, and uv provisions a compatible
# Python itself (reusing a suitable system one, else downloading a managed build).
#
# To install from an unreleased branch, tag, or commit instead of the latest PyPI
# release, set HANGARLLM_CLI_REF:
#   curl -fsSL https://raw.githubusercontent.com/valteresj2/HangarLLM/<branch>/scripts/install.sh | \
#     HANGARLLM_CLI_REF=<branch> sh
#
# NOTE: set -e without pipefail for POSIX sh compatibility (dash on Ubuntu/Debian
# ignores the shebang when invoked as `sh` and does not support `pipefail`).
set -eu

# NOTE: before merging, this must stay as "hangarllm[proxy]" to install from PyPI.
# HANGARLLM_CLI_REF opts into installing from a branch, tag, or commit instead (for
# example, to QA lite autoroute against an unreleased branch, which needs this proxy
# runtime, not the thin hangarllm[cli] install).
if [ -n "${HANGARLLM_CLI_REF:-}" ]; then
  HANGARLLM_PACKAGE="hangarllm[proxy] @ git+https://github.com/valteresj2/HangarLLM.git@${HANGARLLM_CLI_REF}"
else
  HANGARLLM_PACKAGE="hangarllm[proxy]"
fi
UV_VERSION="0.10.9"

# ── colours ────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD='\033[1m'
  GREEN='\033[38;2;78;186;101m'
  GREY='\033[38;2;153;153;153m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' GREY='' RESET=''
fi

info()    { printf "${GREY}  %s${RESET}\n" "$*"; }
success() { printf "${GREEN}  ✔ %s${RESET}\n" "$*"; }
header()  { printf "${BOLD}  %s${RESET}\n" "$*"; }
die()     { printf "\n  Error: %s\n\n" "$*" >&2; exit 1; }

# ── banner ─────────────────────────────────────────────────────────────────
echo ""
cat << 'EOF'
  ██╗     ██╗████████╗███████╗██╗     ██╗     ███╗   ███╗
  ██║     ██║╚══██╔══╝██╔════╝██║     ██║     ████╗ ████║
  ██║     ██║   ██║   █████╗  ██║     ██║     ██╔████╔██║
  ██║     ██║   ██║   ██╔══╝  ██║     ██║     ██║╚██╔╝██║
  ███████╗██║   ██║   ███████╗███████╗███████╗██║ ╚═╝ ██║
  ╚══════╝╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝
EOF
printf "  ${BOLD}HangarLLM Installer${RESET}  ${GREY}— unified gateway for 100+ LLM providers${RESET}\n\n"

# ── OS detection ───────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin)  PLATFORM="macOS ($ARCH)" ;;
  Linux)   PLATFORM="Linux ($ARCH)" ;;
  *)       die "Unsupported OS: $OS. HangarLLM supports macOS and Linux." ;;
esac

info "Platform: $PLATFORM"

# ── uv detection / install ────────────────────────────────────────────────
UV_BIN=""
CURRENT_UV_VERSION=""
for candidate in uv "$HOME/.local/bin/uv"; do
  if command -v "$candidate" >/dev/null 2>&1; then
    UV_BIN="$(command -v "$candidate")"
    break
  elif [ -x "$candidate" ]; then
    UV_BIN="$candidate"
    break
  fi
done

if [ -n "$UV_BIN" ]; then
  CURRENT_UV_VERSION="$("$UV_BIN" --version 2>/dev/null | awk '{print $2}' | head -1 || true)"
fi

if [ -z "$UV_BIN" ] || [ "${CURRENT_UV_VERSION:-}" != "$UV_VERSION" ]; then
  header "Installing uv…"
  if [ -n "${CURRENT_UV_VERSION:-}" ]; then
    info "Upgrading uv from ${CURRENT_UV_VERSION} to ${UV_VERSION}"
  fi
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_NO_MODIFY_PATH=1 sh \
    || die "uv installation failed. Try manually: curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh"
  UV_BIN="$HOME/.local/bin/uv"
fi

# ── install ────────────────────────────────────────────────────────────────
echo ""
if [ -n "${HANGARLLM_CLI_REF:-}" ]; then
  header "Installing hangarllm[proxy] from ${HANGARLLM_CLI_REF}…"
else
  header "Installing hangarllm[proxy]…"
fi
echo ""

# --python mirrors requires-python in pyproject.toml (keep in sync): uv selects the
# interpreter before resolving, so an unconstrained request accepts a too-old system
# Python (stock macOS ships 3.9) and fails resolution instead of downloading a
# managed one. --python-preference system still reuses a compatible system Python.
"$UV_BIN" tool install --python '>=3.10,<3.15' --python-preference system --force "${HANGARLLM_PACKAGE}" \
  || die "uv tool install failed. Try manually: $UV_BIN tool install --python '>=3.10,<3.15' '${HANGARLLM_PACKAGE}'"

# ── find the hangarllm binary installed by uv tool ───────────────────────────
SCRIPTS_DIR="$("$UV_BIN" tool dir --bin)"
HANGARLLM_BIN="${SCRIPTS_DIR}/hangarllm"

if [ ! -x "$HANGARLLM_BIN" ]; then
  die "hangarllm binary not found after install. Try: $UV_BIN tool install '${HANGARLLM_PACKAGE}'"
fi

# ── success banner ─────────────────────────────────────────────────────────
echo ""
success "HangarLLM installed"

installed_ver="$("$HANGARLLM_BIN" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
[ -n "$installed_ver" ] && info "Version: $installed_ver"

# ── PATH hint ──────────────────────────────────────────────────────────────
if ! command -v hangarllm >/dev/null 2>&1; then
  info "Note: add hangarllm to your PATH:  export PATH=\"\$PATH:${SCRIPTS_DIR}\""
fi

# ── launch setup wizard ────────────────────────────────────────────────────
echo ""
printf "  ${BOLD}Run the interactive setup wizard?${RESET} ${GREY}(Y/n)${RESET}: "
# /dev/tty may be unavailable in Docker/CI — default to yes if it can't be read
answer=""
if [ -r /dev/tty ]; then
  read -r answer </dev/tty || answer=""
fi

if [ -z "$answer" ] || [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
  echo ""
  # Use /dev/tty for interactive input when available (stdin is a pipe from curl)
  if [ -r /dev/tty ]; then
    exec "$HANGARLLM_BIN" --setup </dev/tty
  else
    exec "$HANGARLLM_BIN" --setup
  fi
else
  echo ""
  header "Quick start:"
  echo ""
  info "  hangarllm --setup          # interactive wizard"
  info "  hangarllm --model gpt-4o   # single-model quickstart"
  echo ""
  info "Docs: https://github.com/valteresj2/HangarLLM#readme"
  echo ""
fi
