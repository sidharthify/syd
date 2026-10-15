#!/usr/bin/env python3

# syd
# Copyright (c) 2026 Siddhi.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import os
import re
import sys
import json
import stat
import shutil
import tempfile
import datetime
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from colorama import Fore, Style, init

init(autoreset=True)

# ------------------------------------------------------------
# COLORS AND CONSTANTS
# ------------------------------------------------------------

INFO = f"{Fore.BLUE}syd:{Style.RESET_ALL}"
SUCCESS = f"{Fore.GREEN}SUCCESS:{Style.RESET_ALL}"
ERROR = f"{Fore.RED}ERROR:{Style.RESET_ALL}"

COMMANDS = {"install", "remove", "comment", "search", "has", "list"}

# The nix binary used for evaluation and search. The flake wrapper puts
# pkgs.nix on PATH, so shutil.which finds it there. The absolute path is a
# fallback for running syd straight from a checkout on NixOS.
NIX = shutil.which("nix") or "/run/current-system/sw/bin/nix"

# A marker line tells syd where it may write. The bare form '# syd' is the
# default section, and '# syd <label>' names one so a single file can hold
# several independent sections. The closing line '# syd-end' is optional and
# only needed when a section must stop before a blank line or the list's
# closing bracket.
MARKER_RE = re.compile(r"^[ \t]*#[ \t]*syd(?:[ \t]+(?P<label>[A-Za-z0-9._-]+))?[ \t]*$")
END_MARKER_RE = re.compile(r"^[ \t]*#[ \t]*syd-end[ \t]*$")

# Package names share characters with the text around them, so a plain
# substring test would match 'vim' inside 'vimPlugins'. These lookarounds
# only accept a whole entry.
PKG_EDGE = r"[A-Za-z0-9_.-]"

# When syd runs with sudo, SUDO_USER holds the original user's name. We use
# that to resolve their real home instead of /root, falling back to
# Path.home() when not running under sudo.
sudo_user = os.environ.get("SUDO_USER")
if sudo_user and sudo_user != "root":
    real_home = Path(f"/home/{sudo_user}")
else:
    real_home = Path.home()

# Respects XDG_CONFIG_HOME when set. mkdir runs at import time so the config
# dir exists before any command tries to read or write it.
config_base = os.getenv("XDG_CONFIG_HOME", real_home / ".config")
CONFIG_DIR = Path(config_base) / "syd"
CONFIG_FILE = CONFIG_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# ERRORS
# ------------------------------------------------------------

class MarkerMissing(Exception):
    '''Raised when the target file has no '# syd' marker at all.'''


class SectionAmbiguous(Exception):
    '''Raised when several markers exist and no section was named.'''

    def __init__(self, labels):
        super().__init__(labels)
        self.labels = labels


class SectionMissing(Exception):
    '''Raised when the named section is not present in the file.'''

    def __init__(self, section, labels):
        super().__init__(section)
        self.section = section
        self.labels = labels


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

def ask(prompt: str):
    '''
    Reads a stripped line from the user. Returns None on end of input or an
    interrupt so callers can decide whether that means "cancel" or "abort".
    '''
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def load_config() -> dict:
    '''
    Reads the config file into a dict. Keys are left out when absent so the
    caller can tell whether a value was ever set. The old `packages_file` key
    is accepted as `target` so existing setups keep working.
    '''
    config = {}
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            config[key.strip()] = value.strip()

    if "target" not in config and "packages_file" in config:
        config["target"] = config["packages_file"]

    return config


def save_config(config: dict):
    '''Writes the config dict back to disk as plain key=value lines.'''
    content = "".join(f"{key}={config[key]}\n" for key in sorted(config))
    CONFIG_FILE.write_text(content)


def reset_config():
    '''
    Deletes the config file so the next run prompts for the target file and
    rebuild command again.
    '''
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print(f"{INFO} Config reset. Next run will ask for a target file and rebuild command again.")
    else:
        print(f"{ERROR} No config file found at {CONFIG_FILE}")


def resolve_target(config: dict, target_opt, section_opt):
    '''
    Works out which file and section a command should touch. A target on the
    command line wins, otherwise the saved default is used, otherwise the user
    is asked once and the answer is saved. The value may carry a section after
    a '#' so --target foo.nix#gui also selects the section.
    '''
    target = target_opt
    section = section_opt

    if target and "#" in target:
        target, _, inline = target.partition("#")
        if not section:
            section = inline

    if target:
        target = str(Path(target).expanduser())
    elif config.get("target"):
        target = str(Path(config["target"]).expanduser())

    if not target:
        target = ask(f"{INFO} Enter the nix file that holds your '# syd' marker: ")
        if not target:
            print(f"{ERROR} No file entered.")
            sys.exit(1)
        target = str(Path(target).expanduser())
        if not Path(target).exists():
            print(f"{ERROR} File not found: {target}")
            sys.exit(1)
        config["target"] = target
        save_config(config)
        print(f"{SUCCESS} Saved config to {CONFIG_FILE}")

    if section is None:
        section = config.get("section") or None

    return target, section


def resolve_rebuild(config: dict) -> str:
    '''
    Returns the rebuild command, prompting once and saving it when the config
    has none yet. Kept lazy so read-only commands never ask for it.
    '''
    rebuild = config.get("rebuild_cmd")
    if not rebuild:
        rebuild = ask(
            f"{INFO} Enter your rebuild command (for example: sudo nixos-rebuild switch): "
        )
        if not rebuild:
            print(f"{ERROR} No rebuild command entered.")
            sys.exit(1)
        config["rebuild_cmd"] = rebuild
        save_config(config)

    return rebuild


# ------------------------------------------------------------
# FILE AND MARKER HANDLING
# ------------------------------------------------------------

def read_target(path: str) -> list:
    '''Reads the target file as a list of lines, keeping the line endings.'''
    try:
        return Path(path).read_text().splitlines(keepends=True)
    except FileNotFoundError:
        print(f"{ERROR} File not found: {path}")
        sys.exit(1)


def write_target(path: str, lines: list):
    '''
    Writes the lines back to the target. The write goes through a temporary
    file in the same directory and is then renamed over the real path, so an
    interrupted run cannot leave a half-written config. The original mode and
    owner are copied onto the replacement, and the real path is resolved first
    so a symlinked config is followed rather than replaced by a plain file.
    '''
    real = os.path.realpath(path)

    try:
        info = os.stat(real)
        directory = os.path.dirname(real) or "."
        handle, tmp = tempfile.mkstemp(dir=directory, prefix=".syd-")
    except OSError:
        # A read-only directory blocks the temp file, so fall back to a direct
        # write. The file itself was already checked for write permission.
        with open(real, "w") as handle:
            handle.writelines(lines)
        return

    try:
        with os.fdopen(handle, "w") as stream:
            stream.writelines(lines)
        try:
            os.chown(tmp, info.st_uid, info.st_gid)
        except OSError:
            pass
        os.chmod(tmp, stat.S_IMODE(info.st_mode))
        os.replace(tmp, real)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def marker_label(line: str):
    '''
    Returns the section label for a marker line, an empty string for the bare
    '# syd', or None when the line is not a section start.
    '''
    if END_MARKER_RE.match(line):
        return None
    match = MARKER_RE.match(line)
    if not match:
        return None
    return match.group("label") or ""


def is_block_end(line: str) -> bool:
    '''
    True when a line closes the current section. A blank line or the ']' that
    ends a nix list both mark the boundary; package entries never start with
    those characters.
    '''
    stripped = line.strip()
    return stripped == "" or stripped.startswith("]")


def label_text(label: str) -> str:
    '''Renders a section label for messages, naming the bare marker default.'''
    return label or "default"


def find_section(lines: list, section):
    '''
    Finds the managed section and returns (marker_index, end_index) where the
    end is exclusive. Raises MarkerMissing, SectionAmbiguous or SectionMissing
    so the caller can explain what to do. The name "default" selects the bare
    '# syd' marker.
    '''
    if section == "default":
        section = ""

    markers = []
    for index, line in enumerate(lines):
        label = marker_label(line)
        if label is not None:
            markers.append((index, label))

    if not markers:
        raise MarkerMissing

    if section is None:
        if len(markers) > 1:
            labels = ", ".join(label_text(label) for _, label in markers)
            raise SectionAmbiguous(labels)
        start = markers[0][0]
    else:
        start = next((index for index, label in markers if label == section), None)
        if start is None:
            labels = ", ".join(label_text(label) for _, label in markers)
            raise SectionMissing(section, labels)

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if END_MARKER_RE.match(lines[index]):
            end = index
            break
        if marker_label(lines[index]) is not None:
            end = index
            break
        if is_block_end(lines[index]):
            end = index
            break

    return start, end


def locate_section(target: str, section):
    '''
    Reads the target and finds the section, printing a helpful message on
    failure. Returns (lines, start, end) or None when the section is unusable.
    '''
    lines = read_target(target)

    try:
        start, end = find_section(lines, section)
    except MarkerMissing:
        print(f"{ERROR} No '# syd' marker found in {target}")
        print(f"{INFO} Add a '# syd' line where packages should be written, then retry.")
        return None
    except SectionAmbiguous as exc:
        print(f"{ERROR} Several '# syd' sections in {target}: {exc.labels}")
        print(f"{INFO} Pick one with --section <name>.")
        return None
    except SectionMissing as exc:
        print(f"{ERROR} No '# syd {label_text(exc.section)}' section in {target}")
        print(f"{INFO} Available sections: {exc.labels}")
        return None

    return lines, start, end


def section_indent(lines: list, start: int, end: int) -> str:
    '''
    Returns the indentation used by the section so new entries line up with
    the existing ones. An empty section falls back to the marker's own indent,
    which is where the entries will sit.
    '''
    for index in range(start + 1, end):
        text = lines[index]
        if text.strip() and not text.lstrip().startswith("#"):
            return text[:len(text) - len(text.lstrip())]

    marker = lines[start]
    return marker[:len(marker) - len(marker.lstrip())]


def pkg_pattern(pkg: str) -> str:
    '''Builds a regex that matches a package name as a whole entry.'''
    return rf"(?<!{PKG_EDGE}){re.escape(pkg)}(?!{PKG_EDGE})"


def pkg_match(pkg: str, line: str) -> bool:
    '''True when the line holds the package as a complete entry.'''
    return re.search(pkg_pattern(pkg), line) is not None


# ------------------------------------------------------------
# NIX HELPERS
# ------------------------------------------------------------

def check_pkg_exists(pkg: str) -> bool:
    '''
    Checks whether a package exists in nixpkgs by evaluating its .name
    attribute. Every derivation has a root .name, which is more reliable than
    .meta.name (some packages such as the kde ones do not set it).
    '''
    result = subprocess.run(
        [
            NIX,
            "--extra-experimental-features", "nix-command",
            "--extra-experimental-features", "flakes",
            "eval",
            f"nixpkgs#{pkg}.name",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def nix_string(value: str) -> str:
    '''Escapes a Python string for use inside a Nix string literal.'''
    return value.replace("\\", "\\\\").replace('"', '\\"')


def check_pkgs_batch(pkgs) -> dict:
    '''
    Checks a whole list of packages with one nix evaluation and returns
    {pkg: bool}, or None when the result cannot be trusted and the caller
    should fall back to checking them one by one.

    A single eval matters because loading nixpkgs is the expensive part. One
    process for the list replaces one process per package, which cuts both the
    wall time and the memory and CPU spent on multi-package commands.
    '''
    names = " ".join(f'"{nix_string(pkg)}"' for pkg in pkgs)
    expression = (
        'let flake = builtins.getFlake "nixpkgs"; '
        'pkgs = flake.legacyPackages.${builtins.currentSystem}; '
        'in map (n: if pkgs ? ${n} then pkgs.${n}.name else null) '
        f'[ {names} ]'
    )

    result = subprocess.run(
        [
            NIX,
            "--extra-experimental-features", "nix-command",
            "--extra-experimental-features", "flakes",
            "eval", "--json", "--impure", "--expr", expression,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(values, list) or len(values) != len(pkgs):
        return None

    return {pkg: value is not None for pkg, value in zip(pkgs, values)}


def check_pkgs_one_by_one(pkgs) -> dict:
    '''
    Fallback path that evaluates each package separately, spread over a worker
    per package. Kept for the rare cases the batch eval cannot answer.
    '''
    workers = min(len(pkgs), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_pkg_exists, pkg): pkg for pkg in pkgs}
        return {futures[future]: future.result() for future in as_completed(futures)}


def check_pkgs(pkgs) -> dict:
    '''
    Checks several packages and returns {pkg: bool}, preferring the single
    batched eval and falling back to per-package checks when it fails.
    '''
    pkgs = list(pkgs)
    if not pkgs:
        return {}

    results = check_pkgs_batch(pkgs)
    if results is None:
        results = check_pkgs_one_by_one(pkgs)
    return results


def find_similar_packages(pkg: str) -> dict:
    '''
    Runs `nix search nixpkgs <pkg> --json` and returns {name: description}
    sorted so the closest matches come first. The score prefers exact and
    prefix matches and penalises longer names and names with more hyphens, so
    cleaner names float to the top. Returns an empty dict on failure.
    '''
    print(f"{INFO} '{pkg}' not found exactly. Searching nixpkgs for similar packages (this may take a moment)...")
    result = subprocess.run(
        [NIX, "search", "nixpkgs", pkg, "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    packages = {}
    for key, value in data.items():
        parts = key.split(".")
        if len(parts) >= 3:
            name = ".".join(parts[2:])
            packages[name] = value.get("description", "No description")

    needle = pkg.lower()

    def score(name):
        lowered = name.lower()
        points = 0
        if needle == lowered:
            points -= 1000
        elif lowered.startswith(needle):
            points -= 500
        elif needle in lowered:
            if f"-{needle}" in lowered or f"_{needle}" in lowered:
                points -= 300
            else:
                points -= 100
        else:
            points += 500

        points += len(lowered) * 2
        points += lowered.count("-") * 10
        return points

    ordered = sorted(packages, key=score)
    return {name: packages[name] for name in ordered}


def choose_similar(pkg: str):
    '''
    Shows up to ten similar packages and returns the chosen name, or None
    when the user cancels or nothing is found. Shared by install and search so
    the prompt behaves the same in both.
    '''
    similar = find_similar_packages(pkg)
    if not similar:
        print(f"{ERROR} Package '{pkg}' not found in nixpkgs, and no similar packages found.")
        return None

    print(f"\n{INFO} Did you mean:")
    names = list(similar)[:10]
    for index, name in enumerate(names, 1):
        print(f"  {index}) {name} - {similar[name]}")

    choice = ask(f"\n{INFO} Enter the number to install, or 0 to cancel: ")
    if choice is None:
        print(f"{INFO} Cancelled.")
        return None

    if not choice.isdigit():
        print(f"{INFO} Cancelled.")
        return None

    index = int(choice)
    if not 1 <= index <= len(names):
        print(f"{INFO} Cancelled.")
        return None

    return names[index - 1]


# ------------------------------------------------------------
# COMMANDS
# ------------------------------------------------------------

def help():
    '''
    Prints usage, the marker convention, and the current config path.
    '''
    print(f"{INFO} a lightweight declarative package manager for NixOS\n")
    print(f"{Fore.GREEN}USAGE:{Style.RESET_ALL}")
    print("  sudo syd install [options] <package> [more packages]")
    print("  sudo syd remove  [options] <package> [more packages]")
    print("  sudo syd comment [options] <package> [more packages]")
    print("  syd search  <package> [more packages]")
    print("  syd has     [options] <package> [more packages]")
    print("  syd list    [options]")
    print("  syd --reset")
    print("  syd --help\n")

    print(f"{Fore.GREEN}COMMANDS:{Style.RESET_ALL}")
    print("  install       Write packages into the marked section")
    print("  remove        Remove packages from the marked section")
    print("  comment       Comment out packages in the marked section")
    print("  list          List the packages in the marked section")
    print("  search        Search nixpkgs and offer a match to install")
    print("  has           Check whether a package is in the marked section")
    print("  --reset       Forget the stored target file and rebuild command")
    print("  --help        Show this help message and exit\n")

    print(f"{Fore.GREEN}OPTIONS:{Style.RESET_ALL}")
    print("  -t, --target <file>     Edit a different file (default comes from config)")
    print("  -s, --section <name>    Pick a named section when a file has several\n")

    print(f"{Fore.GREEN}HOW IT WORKS:{Style.RESET_ALL}")
    print("  Put a '# syd' line where packages should go, for example:\n")
    print("    environment.systemPackages = with pkgs; [")
    print("      # syd")
    print("    ];\n")
    print("  syd only writes inside that section, so it does not need a packages.nix")
    print("  file of its own. Name a section with '# syd <label>' to keep several")
    print("  lists in one file, and end one early with '# syd-end' when needed.")
    print("  The bare marker answers to the name 'default'.\n")

    print(f"{Fore.GREEN}EXAMPLES:{Style.RESET_ALL}")
    print("  sudo syd install vim htop curl")
    print("  syd list")
    print("  syd install --target ~/nix/home.nix firefox")
    print("  syd install --section gui firefox\n")

    print(f"{INFO} Current config file: {CONFIG_FILE}")


def install_pkgs(config: dict, pkgs, target: str, section) -> int:
    '''
    Writes packages into the marked section. The file is read once and each
    package is checked against the section before being inserted; packages
    that are not found exactly go through the similar-package prompt. The file
    is written back once when anything changed.
    '''
    located = locate_section(target, section)
    if located is None:
        return 1
    lines, start, end = located

    block = lines[start + 1:end]
    pending = []
    for pkg in pkgs:
        if any(pkg_match(pkg, line) for line in block):
            print(f"{INFO} {ERROR} {pkg} already listed.")
        else:
            pending.append(pkg)

    results = check_pkgs(pending)
    indent = section_indent(lines, start, end)
    added = []

    for pkg in pending:
        resolved = pkg if results[pkg] else choose_similar(pkg)
        if resolved is None:
            continue
        if any(pkg_match(resolved, line) for line in block):
            print(f"{INFO} {ERROR} {resolved} already listed.")
            continue

        entry = f"{indent}{resolved}\n"
        lines.insert(start + 1, entry)
        block.insert(0, entry)
        added.append(resolved)
        print(f"{SUCCESS} Added '{resolved}' to {target}")

    if added:
        write_target(target, lines)
        rebuild_prompt(config)

    return 0


def remove_pkgs(config: dict, pkgs, target: str, section) -> int:
    '''
    Removes packages from the marked section. Only lines inside the section
    are touched, so unrelated parts of the file stay as they are.
    '''
    located = locate_section(target, section)
    if located is None:
        return 1
    lines, start, end = located

    block = lines[start + 1:end]
    removed_any = False

    for pkg in pkgs:
        kept = [line for line in block if not pkg_match(pkg, line)]
        if len(kept) == len(block):
            print(f"{ERROR} Package '{pkg}' not found in {target}.")
        else:
            block = kept
            removed_any = True
            print(f"{SUCCESS} Removed {pkg}")

    if removed_any:
        lines[start + 1:end] = block
        write_target(target, lines)
        rebuild_prompt(config)

    return 0


def comment_pkgs(config: dict, pkgs, target: str, section) -> int:
    '''
    Comments out packages in the marked section. A line that is already a
    comment is left alone so the operation stays idempotent.
    '''
    located = locate_section(target, section)
    if located is None:
        return 1
    lines, start, end = located

    block = lines[start + 1:end]
    changed = False

    for pkg in pkgs:
        pattern = pkg_pattern(pkg)
        updated = []
        matched = False
        for line in block:
            if not line.lstrip().startswith("#") and re.search(pattern, line):
                line = re.sub(pattern, f"# {pkg}", line, count=1)
                matched = True
            updated.append(line)

        if matched:
            block = updated
            changed = True
            print(f"{SUCCESS} Commented out {pkg}")
        else:
            print(f"{ERROR} Package '{pkg}' not found in {target}.")

    if changed:
        lines[start + 1:end] = block
        write_target(target, lines)
        rebuild_prompt(config)

    return 0


def list_pkgs(target: str, section) -> int:
    '''
    Prints the active (non-commented) packages in the marked section and a
    total count at the end.
    '''
    located = locate_section(target, section)
    if located is None:
        return 1
    lines, start, end = located

    print(f"{INFO} Packages listed in {target}:")
    pkgs = [
        line.strip()
        for line in lines[start + 1:end]
        if line.strip() and not line.strip().startswith("#")
    ]

    if not pkgs:
        print(f"{INFO} No packages found.")
    else:
        for pkg in pkgs:
            print(f"  {pkg}")

    print(f"\n{INFO} Total packages: {len(pkgs)}")
    return 0


def has_pkgs(target: str, section, pkgs) -> int:
    '''
    Reports whether each package appears in the marked section. A commented
    entry still counts as listed.
    '''
    located = locate_section(target, section)
    if located is None:
        return 1
    lines, start, end = located
    block = lines[start + 1:end]

    for pkg in pkgs:
        if any(pkg_match(pkg, line) for line in block):
            print(f"{SUCCESS} Yes. '{pkg}' exists in {target}")
        else:
            print(f"{ERROR} Could not find '{pkg}' in {target}")

    return 0


def search_pkgs(config: dict, pkgs, target_opt, section_opt) -> int:
    '''
    Searches nixpkgs for each package. Exact matches are confirmed, and a
    miss offers the similar-package prompt. A chosen package is installed,
    re-invoking syd through sudo when the caller is not root.
    '''
    results = check_pkgs(pkgs)

    for pkg in pkgs:
        if results[pkg]:
            print(f"{SUCCESS} '{pkg}' exists in nixpkgs.")
            continue

        selected = choose_similar(pkg)
        if selected is None:
            continue

        if os.geteuid() != 0:
            print(f"{INFO} Elevating permissions to install...")
            program = sys.argv[0]
            if not os.path.isabs(program):
                program = shutil.which(program) or program
            command = ["sudo", program, "install"]
            if target_opt:
                command += ["--target", target_opt]
            if section_opt:
                command += ["--section", section_opt]
            command.append(selected)

            env = os.environ.copy()
            env["PATH"] = "/run/wrappers/bin:/usr/local/bin:/usr/bin:/bin:/run/current-system/sw/bin"
            subprocess.run(command, env=env)
        else:
            target, section = resolve_target(config, target_opt, section_opt)
            install_pkgs(config, [selected], target, section)

    return 0


def rebuild_prompt(config: dict):
    '''
    Asks whether to run the rebuild command after a change. When already root
    and the command starts with `sudo`, the prefix is stripped to avoid a sudo
    inside a root shell. An nh command is never run as root because nh handles
    escalation itself and breaks otherwise. Exits with code 1 on failure.
    '''
    answer = ask(f"{INFO} Rebuild NixOS? [y/N]: ")
    if answer is None or answer.lower() != "y":
        print(f"{INFO} Skipping rebuild.")
        return

    command = resolve_rebuild(config).strip()

    if _is_nh_command(command):
        if os.geteuid() == 0:
            print(f"{ERROR} '{command}' should not be run as root. nh handles privilege escalation internally.")
            print(f"{INFO} Run syd without sudo when using nh as your rebuild command.")
            return
    elif os.geteuid() == 0 and command.startswith("sudo "):
        command = command.replace("sudo ", "", 1)
        print(f"{INFO} Running (sudo stripped): {command}")

    env = os.environ.copy()
    env["PATH"] = "/run/wrappers/bin:/usr/local/bin:/usr/bin:/bin:/run/current-system/sw/bin"

    print(f"{INFO} Running: {command}")
    if subprocess.run(command, shell=True, env=env).returncode != 0:
        print(f"{ERROR} Rebuild command failed.")
        sys.exit(1)


def _is_nh_command(command: str) -> bool:
    '''True when the rebuild command uses nh, which escalates internally.'''
    return command.strip().startswith("nh ")


# ------------------------------------------------------------
# ARGUMENT PARSING
# ------------------------------------------------------------

def parse_options(args):
    '''
    Pulls --target and --section out of the argument list and returns
    (target, section, remaining). Both long options also accept a value after
    an equals sign.
    '''
    target = None
    section = None
    rest = []
    index = 0

    while index < len(args):
        arg = args[index]
        if arg in ("-t", "--target"):
            index += 1
            if index >= len(args):
                print(f"{ERROR} {arg} needs a value.")
                sys.exit(1)
            target = args[index]
        elif arg.startswith("--target="):
            target = arg.split("=", 1)[1]
        elif arg in ("-s", "--section"):
            index += 1
            if index >= len(args):
                print(f"{ERROR} {arg} needs a value.")
                sys.exit(1)
            section = args[index]
        elif arg.startswith("--section="):
            section = arg.split("=", 1)[1]
        else:
            rest.append(arg)
        index += 1

    return target, section, rest


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    '''
    Entry point. Loads the config once, resolves the target for commands that
    need it, and dispatches to the matching function.
    '''
    today = datetime.date.today()
    if today.month == 1 and today.day == 6:
        print(f"\n\033[1m\033[3m{Fore.BLUE}Shine on, you crazy diamond!\n{Style.RESET_ALL}")

    if len(sys.argv) < 2:
        help()
        sys.exit(0)

    subcommand = sys.argv[1]
    args = sys.argv[2:]

    if subcommand in ("--help", "-h"):
        if args:
            print(f"{INFO} Usage: syd --help")
            sys.exit(1)
        help()
        sys.exit(0)

    if subcommand == "--reset":
        if args:
            print(f"{INFO} Usage: syd --reset")
            sys.exit(1)
        reset_config()
        sys.exit(0)

    if subcommand not in COMMANDS:
        print(f"{INFO} Unknown command: {subcommand}")
        print("Run 'syd --help' for usage.")
        sys.exit(1)

    target_opt, section_opt, rest = parse_options(args)
    config = load_config()

    if subcommand == "search":
        if not rest:
            print(f"{INFO} Usage: syd search <package> [more packages]")
            sys.exit(1)
        sys.exit(search_pkgs(config, rest, target_opt, section_opt))

    target, section = resolve_target(config, target_opt, section_opt)

    if subcommand in ("install", "remove", "comment") and not os.access(target, os.W_OK):
        print(f"{ERROR} Cannot write to {target}")
        if _is_nh_command(config.get("rebuild_cmd", "")):
            print(f"{INFO} Check the file permissions: chmod u+w {target}")
        else:
            print(f"{INFO} Try: sudo syd {subcommand} <package>")
        sys.exit(1)

    if subcommand == "install":
        if not rest:
            print(f"{INFO} Usage: syd install <package> [more packages]")
            sys.exit(1)
        sys.exit(install_pkgs(config, rest, target, section))

    if subcommand == "remove":
        if not rest:
            print(f"{INFO} Usage: syd remove <package> [more packages]")
            sys.exit(1)
        sys.exit(remove_pkgs(config, rest, target, section))

    if subcommand == "comment":
        if not rest:
            print(f"{INFO} Usage: syd comment <package> [more packages]")
            sys.exit(1)
        sys.exit(comment_pkgs(config, rest, target, section))

    if subcommand == "list":
        if rest:
            print(f"{INFO} Usage: syd list")
            sys.exit(1)
        sys.exit(list_pkgs(target, section))

    if subcommand == "has":
        if not rest:
            print(f"{INFO} Usage: syd has <package> [more packages]")
            sys.exit(1)
        sys.exit(has_pkgs(target, section, rest))


if __name__ == "__main__":
    main()
