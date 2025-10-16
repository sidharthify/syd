#!/usr/bin/env zsh
set -e

PACKAGES="/etc/nixos/packages/packages.nix"

# colors
RED='\033[0;31m'
BLUE='\033[1;34m'
GREEN='\033[0;32m'
NC='\033[0m'

package=$1

# check input
if [[ -z "$package" ]]; then
  echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} Usage: $0 <package-name>"
  exit 1