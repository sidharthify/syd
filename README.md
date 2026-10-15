# syd

**syd** (named after **Syd Barrett**) is a lightweight command-line tool written in **Python** for managing your NixOS packages declaratively.
It lets you install, remove, list, and search for packages by directly editing your Nix configuration files, so you don’t have to open them manually every time you make a change.

---

## Usage

* `syd install <pkg>`: write packages into the section marked with `# syd`
* `syd remove <pkg>`: remove packages from the marked section
* `syd comment <pkg>`: comment out packages in the marked section
* `syd search <pkg>`: search for a package in nixpkgs
* `syd has <pkg>`: check if a package is listed in the marked section
* `syd list`: print and count the packages in the marked section
* `syd --reset`: forget the stored target file and rebuild command
* `syd --help`: show usage info

Options:

* `-t`, `--target <file>`: edit a different file (the default comes from the config)
* `-s`, `--section <name>`: pick a named section when a file has several markers

### Smart Search & Typo Detection
If you misspell a package or search for a nested package such as `qtwebengine`, **syd** will automatically search nixpkgs and present a "Did you mean:" interactive menu. You can pick the correct package from the list to install it immediately. (This is probably my favourite feature)

That search runs against a local index of nixpkgs stored under `~/.cache/syd`. The index is built once per nixpkgs version, which takes a few seconds, and after that every search is a local lookup instead of a nixpkgs evaluation. Delete the cache directory to force a rebuild.

The config is stored in `~/.config/syd/config`, which remembers:

* the default target file that holds your `# syd` marker
* your rebuild command (for example `sudo nixos-rebuild switch`)

---

## Installation

You can install **syd** directly from its flake or use a development shell if you’re contributing or testing it.

---

### System-wide installation (via flake)

In your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    syd.url = "github:sidharthify/syd";
  };

  outputs = { self, nixpkgs, syd, ... }: {
    nixosConfigurations.your-hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        ({ pkgs, ... }: {
          environment.systemPackages = with pkgs; [
            syd.packages.x86_64-linux.default
          ];
        })
      ];
    };
  };
}
```

Then rebuild your system:

```bash
sudo nixos-rebuild switch --flake .#your-hostname
```

Now you can use **syd** globally:

```bash
syd install firefox
syd remove vim
syd search discord
```

---

### Nix Shell

If you want to test your changes on syd or just run it directly, use the flake’s devShell:

```bash
nix develop github:sidharthify/syd
```

This drops you into a shell with all Python dependencies ready.
Then you can run:

```bash
python syd.py --help
```

or make it executable and run it directly:

```bash
chmod +x syd.py
./syd.py install htop
```

---

### Home Manager

If you’re using Home Manager, add syd as a package input:

```nix
home.packages = [
  inputs.syd.packages.x86_64-linux.default
];
```

Then rebuild your home configuration:

```bash
home-manager switch --flake ~/.config/nixpkgs
```

You can confirm syd is installed with:

```bash
syd --help
```

---

## Setting up your configuration

Put a `# syd` line wherever you want syd to write packages. That can be a list
you already have, so a separate file is not required:

```nix
environment.systemPackages = with pkgs; [
  # syd
];
```

syd only writes between that marker and the end of the section. A section
stops at a blank line, the list's closing bracket, or an explicit `# syd-end`
line. You can also name a section, which is handy when a file holds more than
one list:

```nix
home.packages = with pkgs; [
  # syd gui
  firefox
  # syd-end

  # syd cli
  git
];
```

Named sections are picked with `--section gui` or `--section cli`. To point at
a different file for one command, use `--target ~/nix/home.nix`. The path can
also carry the section name, as in `--target ~/nix/home.nix#gui`.

---

## Notes

* syd was originally written in bash but is now entirely in **Python 3**, making it a lot faster.
* It writes into the section marked with `# syd`, so it can manage a list inside any Nix file.
For reference, see [my NixOS setup](https://github.com/sidharthify/nixos-configs) to understand how I structure my configs. (not the best, I'm aware)

* An overview of syd's code can be found on [this blog](https://sidharthify.me/blogs/blog-18-10-25).
