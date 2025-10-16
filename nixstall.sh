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

# nixstall
for pkg in "$@"; do
  # check if package already exists in the file
  if grep -q "\b${pkg}\b" "$PACKAGES"; then
    echo -e "${BLUE}Nixstall:${NC} ${RED}SKIP:${NC} ${pkg} already listed"
    continue
  fi

  # check if package actually exists in nixpkgs
  if nix eval nixpkgs#"$pkg" &>/dev/null; then
    sudo sed -i "\$i\    ${pkg}" "${PACKAGES}"
    echo -e "${BLUE}Nixstall:${NC} ${GREEN}ADDED:${NC} ${pkg}"
  else
    echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} Package '${pkg}' not found in nixpkgs"
  fi
done