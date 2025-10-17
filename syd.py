#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

# ------------------------------------------------------------
# COLORS AND CONSTANTS
# ------------------------------------------------------------

INFO = f"{Fore.BLUE}syd:{Style.RESET_ALL}"
SUCCESS = f"{Fore.GREEN}SUCCESS:{Style.RESET_ALL}"
ERROR = f"{Fore.RED}ERROR:{Style.RESET_ALL}"

config_base = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
CONFIG_DIR = Path(config_base) / "syd"
CONFIG_FILE = CONFIG_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# FUNCTIONS
# ------------------------------------------------------------

def help():
    print(f"{INFO} a lightweight declarative package manager for NixOS\n")
    print(f"{Fore.GREEN}USAGE:{Style.RESET_ALL}")
    print("  syd install <package> [more packages]")
    print("  syd remove  <package> [more packages]")
    print("  syd search  <package> [more packages]")
    print("  syd list")
    print("  syd --reset")
    print("  syd --help\n")

    print(f"{Fore.GREEN}COMMANDS:{Style.RESET_ALL}")
    print("  install       Add one or more packages to your nix packages file")
    print("  remove        Remove one or more packages from your nix packages file")
    print("  list          Show all packages currently listed in your nix file")
    print("  search        Search for packages in nixpkgs")
    print("  --reset       Reset stored packages file path and rebuild command")
    print("  --help        Show this help message and exit\n")

    print(f"{Fore.GREEN}EXAMPLES:{Style.RESET_ALL}")
    print("  syd install firefox")
    print("  syd install vim htop curl")
    print("  syd remove neovim")
    print("  syd remove neovim htop curl")
    print("  syd search discord")
    print("  syd search htop neovim curl\n")

    print(f"{INFO} Current config file: {CONFIG_FILE}")

def reset_config():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print(f"{INFO} Config reset. Next run will ask for path and rebuild command again.")
    else:
        print(f"{ERROR} No config file found at {CONFIG_FILE}")

def setup_config():
    PACKAGES = None
    REBUILD = None

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if line.startswith("packages_file="):
                    PACKAGES = line.split("=", 1)[1].strip()
                elif line.startswith("rebuild_cmd="):
                    REBUILD = line.split("=", 1)[1].strip()
    else:
        packages_path = input(f"{INFO} Enter path to your nix packages file: ").strip()
        PACKAGES = Path(packages_path)

        if not PACKAGES.exists():
            print(f"{ERROR} File not found: {PACKAGES}")
            sys.exit(1)

        REBUILD = input(f"{INFO} Enter your rebuild command (e.g. sudo nixos-rebuild switch): ").strip()
        if not REBUILD:
            print(f"{ERROR} No rebuild command entered.")
            sys.exit(1)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        with open(CONFIG_FILE, "w") as f:
            f.write(f"packages_file={PACKAGES}\n")
            f.write(f"rebuild_cmd={REBUILD}\n")

        print(f"{SUCCESS} Saved config to {CONFIG_FILE}")

    return PACKAGES, REBUILD

def rebuild_prompt():
    read = input(f"{INFO} Rebuild NixOS? [y/N]: ").strip().lower()

    if read == 'y':
        print(f"{INFO} Running: {REBUILD}")
        result = subprocess.run(REBUILD, shell=True)
        if result.returncode != 0:
            print(f"{ERROR} Rebuild command failed.")
            sys.exit(1)
    else:
        print(f"{INFO} Skipping rebuild.")

def install_pkgs(*pkgs):
    for pkg in pkgs:
        if any(pkg in line.split() for line in open(PACKAGES)):
            print(f"{INFO} {ERROR} {pkg} already listed.")
            continue

        result = subprocess.run(
            [
                "nix", "--extra-experimental-features", "nix-command",
                "--extra-experimental-features", "flakes",
                "eval", f"github:NixOS/nixpkgs/nixos-unstable#{pkg}.meta.name"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            subprocess.run( # use sed directly cuz it's easier
                [
                    "sudo", "sed", "-i",
                    f"$i\\  {pkg}",
                    str(PACKAGES)
                ],
                check=True
            )
            print(f"{SUCCESS} Added '{pkg}' to {PACKAGES}")
        else:
            print(f"{ERROR} Package '{pkg}' not found in nixpkgs.")

    rebuild_prompt()

def remove_pkgs(*pkgs):
    for pkg in pkgs:
        if any(pkg in line.split() for line in open(PACKAGES)):
            subprocess.run(
                [
                    "sudo", "sed", "-i", "-E",
                    f"/\\b{pkg}\\b/d",
                    str(PACKAGES)
                ],
                check=True
            )
            print(f"{SUCCESS} Removed {pkg}")
        else:
            print(f"{ERROR} Package '{pkg}' not found in config")
    
    rebuild_prompt()

def list_pkgs():
    print(f"{INFO} Packages listed in {PACKAGES}:")

    with open(PACKAGES, "r") as f:
        lines = f.readlines()

    pkgs = [
        line.strip()
        for line in lines
        if line.strip()
        and not line.strip().startswith("#")
        and "[" not in line and "]" not in line
    ]

    if not pkgs:
        print(f"{INFO} No packages found.")
    else:
        for pkg in pkgs:
            print(f"  {pkg}")

    print(f"\n{INFO} Total packages: {len(pkgs)}")

def search_pkgs(*pkgs):
    for pkg in pkgs:

        result = subprocess.run(
            [
                "nix", "--extra-experimental-features", "nix-command",
                "--extra-experimental-features", "flakes",
                "eval", f"github:NixOS/nixpkgs/nixos-unstable#{pkg}.meta.name"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            print(f"{INFO} '{pkg}' exists in nixpkgs.")
        else:
            print(f"{ERROR} '{pkg}' not found in nixpkgs.")

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        help()
        sys.exit(0)

    subcommand = sys.argv[1]
    args = sys.argv[2:]

    global PACKAGES, REBUILD
    PACKAGES, REBUILD = setup_config()

    # syd install
    if subcommand == "install":
        PACKAGES, REBUILD = setup_config()
        if len(args) == 0:
            print(f"{INFO} Usage: syd install <package>")
            sys.exit(1)
        install_pkgs(*args)

    # syd remove
    elif subcommand == "remove":
        PACKAGES, REBUILD = setup_config()
        if len(args) == 0:
            print(f"{INFO} Usage: syd remove <package>")
            sys.exit(1)
        remove_pkgs(*args)

    # syd search
    elif subcommand == "search":
        PACKAGES, REBUILD = setup_config()
        if len(args) == 0:
            print(f"{INFO} Usage: syd search <package>")
            sys.exit(1)
        search_pkgs(*args)

    # syd list
    elif subcommand == "list":
        if len(args) != 0:
            print(f"{INFO} Usage: syd list")
            sys.exit(1)
        PACKAGES, REBUILD = setup_config()
        list_pkgs()

    # syd --reset
    elif subcommand == "--reset":
        if len(args) != 0:
            print(f"{INFO} Usage: syd --reset")
            sys.exit(1)
        reset_config()

    # syd --help
    elif subcommand in ["--help", "-h", ""]:
        if len(args) != 0:
            print(f"{INFO} Usage: syd --help")
            sys.exit(1)
        help()

    else:
        print(f"{INFO} Unknown command: {subcommand}")
        print("Run 'syd --help' for usage.")
        sys.exit(1)

if __name__ == "__main__":
    main() # call the main function