#!/usr/bin/env zsh
set -e

# colors
RED='\033[0;31m'
BLUE='\033[1;34m'
GREEN='\033[0;32m'
NC='\033[0m'

# configs for package file
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nixstall"
CONFIG_FILE="$CONFIG_DIR/config"

# print help
help() {
  echo -e "${BLUE}Nixstall - a simple NixOS 'package manager helper'${NC}"
  echo
  echo -e "${GREEN}USAGE:${NC}"
  echo "  nixstall <package> [more packages]"
  echo "  nixstall --reset"
  echo "  nixstall --help"
  echo
  echo -e "${GREEN}COMMANDS:${NC}"
  echo "  <package>     Add one or more packages to your nix packages file"
  echo "  --reset       Reset stored packages file path. This will prompt you to enter it again in the next run."
  echo "  --help        Show this help message and exit"
  echo
  echo -e "${GREEN}EXAMPLES:${NC}"
  echo "  nixstall firefox"
  echo "  nixstall vim htop curl"
  echo "  nixstall --reset"
  echo
  echo -e "${BLUE}Current config file:${NC} $CONFIG_FILE"
}

# parse flags
case "$1" in
  --help|-h)
    help
    exit 0
    ;;
  --reset)
    rm -f "$CONFIG_FILE"
    echo -e "${BLUE}Nixstall:${NC} Config reset. Next run will ask for path again."
    exit 0
    ;;
esac

# reset flag
if [[ "$1" == "--reset" ]]; then
  rm -f "$CONFIG_FILE"
  echo -e "${BLUE}Nixstall:${NC} Config reset. Next run will ask for path again."
  exit 0
fi

# get path
if [[ -f "$CONFIG_FILE" ]]; then
  PACKAGES=$(grep '^packages_file=' "$CONFIG_FILE" | cut -d= -f2-)
else
  echo -ne "${BLUE}Nixstall:${NC} Enter path to your nix packages file: "
  read -r PACKAGES

  if [[ ! -f "$PACKAGES" ]]; then
    echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} File not found: $PACKAGES"
    exit 1
  fi

  mkdir -p "$CONFIG_DIR"
  echo "packages_file=$PACKAGES" > "$CONFIG_FILE"
  echo -e "${BLUE}Nixstall:${NC} Saved path to ${CONFIG_FILE}"
fi

package=$1

# check input
if [[ -z "$package" ]]; then
  echo -e "${BLUE}Nixstall:${NC} Usage: nixstall <package-name>"
  exit 1
fi

# nixstall
for pkg in "$@"; do
  if grep -q -w "$pkg" "$PACKAGES"; then
    echo -e "${BLUE}Nixstall:${NC} ${RED}SKIP:${NC} ${pkg} already listed"
    continue
  fi

  if nix eval "nixpkgs#${pkg}" &>/dev/null; then
    sudo sed -i "\$i\  ${pkg}" "$PACKAGES"
    echo -e "${BLUE}Nixstall:${NC} ${GREEN}ADDED:${NC} ${pkg}"
  else
    echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} Package '${pkg}' not found in nixpkgs"
  fi
done

# nixos-rebuild switch
echo -ne "${BLUE}Nixstall:${NC} Rebuild NixOS? [y/N]: "
read -r input
if [[ "${input:l}" == "y" ]]; then
  sudo nixos-rebuild switch
else
  echo -e "${BLUE}Nixstall:${NC} Skipping rebuild."
fi