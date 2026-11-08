#!/usr/bin/env bash
# colors_and_utils.sh
# Shared ANSI color codes and print helper functions.
# Source this file from every component script.

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

safe_path() { printf '%s' "$1" | tr '\\' '/'; }
print_error() { printf '%b\n' "${RED}[ERROR] $*${NC}" >&2; }
print_ok()    { printf '%b\n' "${GREEN}[OK] $*${NC}"; }
print_warn()  { printf '%b\n' "${YELLOW}[WARN] $*${NC}"; }
