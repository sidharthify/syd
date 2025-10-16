#!/usr/bin/env bash
set -e

# ------------------------------------------------------------
# COLORS AND CONSTANTS
# ------------------------------------------------------------

RED='\033[0;31m'
BLUE='\033[1;34m'
GREEN='\033[0;32m'
NC='\033[0m'

ERROR="${RED}ERROR:${NC}"
INFO="${BLUE}Syd:${NC}"
SUCCESS="${GREEN}SUCCESS:${NC}"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/syd"
CONFIG_FILE="$CONFIG_DIR/config"

# ------------------------------------------------------------
# FUNCTIONS
# ------------------------------------------------------------

help() {
  echo -e "${INFO} a simple NixOS 'package manager helper'"
  echo
  echo -e "${GREEN}USAGE:${NC}"
  echo "  syd install <package> [more packages]"
  echo "  syd remove  <package> [more packages]"
  echo "  syd list"
  echo "  syd --reset"
  echo "  syd --help"
  echo
  echo -e "${GREEN}COMMANDS:${NC}"
  echo "  install       Add one or more packages to your nix packages file"
  echo "  remove        Remove one or more packages from your nix packages file"
  echo "  list          Show all packages currently listed in your nix file"
  echo "  --reset       Reset stored packages file path and rebuild command"
  echo "  --help        Show this help message and exit"
  echo
  echo -e "${GREEN}EXAMPLES:${NC}"
  echo "  syd install firefox"
  echo "  syd install vim htop curl"
  echo "  syd remove neovim"
  echo "  syd remove neovim htop curl"
  echo
  echo -e "${INFO} Current config file: $CONFIG_FILE"
}

reset_config() {
  rm -f "$CONFIG_FILE"
  echo -e "${INFO} Config reset. Next run will ask for path and rebuild command again."
}

setup_config() {
  if [[ -f "$CONFIG_FILE" ]]; then
    PACKAGES=$(grep '^packages_file=' "$CONFIG_FILE" | cut -d= -f2-)
    REBUILD=$(grep '^rebuild_cmd=' "$CONFIG_FILE" | cut -d= -f2-)
  else
    echo -ne "${INFO} Enter path to your nix packages file: "
    read -r PACKAGES
    if [[ ! -f "$PACKAGES" ]]; then
      echo -e "${ERROR} File not found: $PACKAGES"
      exit 1
    fi
    echo -ne "${INFO} Enter your rebuild command (e.g. sudo nixos-rebuild switch): "
    read -r REBUILD
    if [[ -z "$REBUILD" ]]; then
      echo -e "${ERROR} No rebuild command entered."
      exit 1
    fi
    mkdir -p "$CONFIG_DIR"
    {
      echo "packages_file=$PACKAGES"
      echo "rebuild_cmd=$REBUILD"
    } > "$CONFIG_FILE"
    echo -e "${SUCCESS} Saved config to ${CONFIG_FILE}"
  fi
}

install_pkgs() {
  for pkg in "$@"; do
    if grep -q -w "$pkg" "$PACKAGES"; then
      echo -e "${INFO} ${ERROR} ${pkg} already listed"
      continue
    fi
    if nix --extra-experimental-features nix-command --extra-experimental-features flakes \
       eval "github:NixOS/nixpkgs/nixos-unstable#${pkg}.meta.name" &>/dev/null; then
      sudo sed -i "\$i\  ${pkg}" "$PACKAGES"
      echo -e "${SUCCESS} Added ${pkg}"
    else
      echo -e "${ERROR} Package '${pkg}' not found in nixpkgs"
    fi
  done
  rebuild_prompt
}

remove_pkgs() {
  for pkg in "$@"; do
    if grep -q -w "$pkg" "$PACKAGES"; then
      sudo sed -i -E "/\<${pkg}\>/d" "$PACKAGES"
      echo -e "${SUCCESS} Removed ${pkg}"
    else
      echo -e "${ERROR} Package '${pkg}' not found in config"
    fi
  done
  rebuild_prompt
}

list_pkgs() {
  echo -e "${INFO} Packages listed in ${PACKAGES}:"
  pkgs=$(grep -E '^[[:space:]]*[^#[:space:]].+' "$PACKAGES" \
    | grep -vE '(\[|\])' \
    | sed 's/^[[:space:]]*//')

  if [[ -z "$pkgs" ]]; then
    echo "(no packages found)"
  else
    echo "$pkgs"
    count=$(echo "$pkgs" | wc -l)
    echo
    echo -e "${INFO} Total packages: ${GREEN}${count}${NC}"
  fi
}

search_pkgs() {
  local pkg="$1"

  for pkg in "$@"; do
  if nix --extra-experimental-features nix-command --extra-experimental-features flakes \
    eval "github:NixOS/nixpkgs/nixos-unstable#${pkg}.meta.name" &>/dev/null; then
    
    echo -e "${SUCCESS} Package '${pkg}' exists in nixpkgs."
  else
    echo -e "${ERROR} Package '${pkg}' not found in nixpkgs."
  fi
  done
}

rebuild_prompt() {
  echo -ne "${INFO} Rebuild NixOS? [y/N]: "
  read -r input
  if [[ "${input,,}" == "y" ]]; then
    echo -e "${INFO} Running: ${GREEN}${REBUILD}${NC}"
    bash -c "$REBUILD" || {
      echo -e "${ERROR} Rebuild command failed."
      exit 1
    }
  else
    echo -e "${INFO} Skipping rebuild."
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
      echo -e "${ERROR} Usage: syd install <package>"
      exit 1
    fi
    install_pkgs "$@"
    ;;
  remove)
    setup_config
    if [[ $# -eq 0 ]]; then
      echo -e "${ERROR} Usage: syd remove <package>"
      exit 1
    fi
    remove_pkgs "$@"
    ;;
  search)
    setup_config
    if [[ $# -eq 0 ]]; then
      echo -e "${ERROR} Usage: syd search <package>"
      exit 1
    fi
    search_pkgs "$@"
    ;;
  list)
    if [[ $# -ne 0 ]]; then
      echo -e "${ERROR} Usage: syd list"
      exit 1
    fi
    setup_config
    list_pkgs
    ;;
  --reset)
    if [[ $# -ne 0 ]]; then
      echo -e "${ERROR} Usage: syd --reset"
      exit 1
    fi
    reset_config
    ;;
  --help|-h|"")
    if [[ $# -ne 0 ]]; then
      echo -e "${ERROR} Usage: syd --help"
      exit 1
    fi
    help
    ;;
  *)
    echo -e "${ERROR} Unknown command: ${subcommand}"
    echo "Run 'syd --help' for usage."
    exit 1
    ;;
esac