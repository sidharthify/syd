#!/usr/bin/env bash
set -e

RED='\033[0;31m'
BLUE='\033[1;34m'
GREEN='\033[0;32m'
NC='\033[0m'

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nixstall"
CONFIG_FILE="$CONFIG_DIR/config"

# ------------------------------------------------------------
# FUNCTIONS
# ------------------------------------------------------------

help() {
  echo -e "${BLUE}Nixstall - a simple NixOS 'package manager helper'${NC}"
  echo
  echo -e "${GREEN}USAGE:${NC}"
  echo "  nixstall install <package> [more packages]"
  echo "  nixstall remove  <package> [more packages]"
  echo "  nixstall --reset"
  echo "  nixstall --help"
  echo
  echo -e "${GREEN}COMMANDS:${NC}"
  echo "  install       Add one or more packages to your nix packages file"
  echo "  remove        Remove one or more packages from your nix packages file"
  echo "  --reset       Reset stored packages file path and rebuild command"
  echo "  --help        Show this help message and exit"
  echo
  echo -e "${GREEN}EXAMPLES:${NC}"
  echo "  nixstall install firefox"
  echo "  nixstall install vim htop curl"
  echo "  nixstall remove neovim"
  echo "  nixstall --reset"
  echo
  echo -e "${BLUE}Current config file:${NC} $CONFIG_FILE"
}

reset_config() {
  rm -f "$CONFIG_FILE"
  echo -e "${BLUE}Nixstall:${NC} Config reset. Next run will ask for path and rebuild command again."
}

setup_config() {
  if [[ -f "$CONFIG_FILE" ]]; then
    PACKAGES=$(grep '^packages_file=' "$CONFIG_FILE" | cut -d= -f2-)
    REBUILD=$(grep '^rebuild_cmd=' "$CONFIG_FILE" | cut -d= -f2-)
  else
    echo -ne "${BLUE}Nixstall:${NC} Enter path to your nix packages file: "
    read -r PACKAGES
    if [[ ! -f "$PACKAGES" ]]; then
      echo -e "${RED}ERROR:${NC} File not found: $PACKAGES"
      exit 1
    fi
    echo -ne "${BLUE}Nixstall:${NC} Enter your rebuild command (e.g. sudo nixos-rebuild switch): "
    read -r REBUILD
    if [[ -z "$REBUILD" ]]; then
      echo -e "${RED}ERROR:${NC} No rebuild command entered."
      exit 1
    fi
    mkdir -p "$CONFIG_DIR"
    {
      echo "packages_file=$PACKAGES"
      echo "rebuild_cmd=$REBUILD"
    } > "$CONFIG_FILE"
    echo -e "${BLUE}Nixstall:${NC} Saved config to ${CONFIG_FILE}"
  fi
}

install_pkgs() {
  for pkg in "$@"; do
    if grep -q -w "$pkg" "$PACKAGES"; then
      echo -e "${BLUE}Nixstall:${NC} ${RED}SKIP:${NC} ${pkg} already listed"
      continue
    fi
    if nix --extra-experimental-features nix-command --extra-experimental-features flakes \
       eval "github:NixOS/nixpkgs/nixos-unstable#${pkg}.meta.name" &>/dev/null; then
      sudo sed -i "\$i\  ${pkg}" "$PACKAGES"
      echo -e "${BLUE}Nixstall:${NC} ${GREEN}ADDED:${NC} ${pkg}"
    else
      echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} Package '${pkg}' not found in nixpkgs"
    fi
  done
  rebuild_prompt
}

remove_pkgs() {
  for pkg in "$@"; do
    if grep -q -w "$pkg" "$PACKAGES"; then
      sudo sed -i -E "/\<${pkg}\>/d" "$PACKAGES"
      echo -e "${BLUE}Nixstall:${NC} ${GREEN}REMOVED:${NC} ${pkg}"
    else
      echo -e "${BLUE}Nixstall:${NC} ${RED}ERROR:${NC} Package '${pkg}' not found in config"
    fi
  done
  rebuild_prompt
}

rebuild_prompt() {
  echo -ne "${BLUE}Nixstall:${NC} Rebuild NixOS? [y/N]: "
  read -r input
  if [[ "${input,,}" == "y" ]]; then
    echo -e "${BLUE}Nixstall:${NC} Running: ${GREEN}${REBUILD}${NC}"
    bash -c "$REBUILD" || {
      echo -e "${RED}ERROR:${NC} Rebuild command failed."
      exit 1
    }
  else
    echo -e "${BLUE}Nixstall:${NC} Skipping rebuild."
  fi
}

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

subcommand="$1"
shift || true

case "$subcommand" in
  install)
    setup_config
    if [[ $# -eq 0 ]]; then
      echo -e "${RED}ERROR:${NC} Usage: nixstall install <package>"
      exit 1
    fi
    install_pkgs "$@"
    ;;
  remove)
    setup_config
    if [[ $# -eq 0 ]]; then
      echo -e "${RED}ERROR:${NC} Usage: nixstall remove <package>"
      exit 1
    fi
    remove_pkgs "$@"
    ;;
  --reset)
    reset_config
    ;;
  --help|-h|"")
    help
    ;;
  *)
    echo -e "${RED}ERROR:${NC} Unknown command: ${subcommand}"
    echo "Run 'nixstall --help' for usage."
    exit 1
    ;;
esac