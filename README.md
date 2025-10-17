# syd

**syd** (named after **Syd Barrett**) is a lightweight command-line tool written in **Python** for managing your NixOS packages declaratively.
It lets you install, remove, list, and search for packages by directly editing your Nix configuration files, so you don’t have to open them manually every time you make a change.

---

## Usage

* `syd install <pkg>` — add one or more packages to your saved Nix config
* `syd remove <pkg>` — remove one or more packages from your config
* `syd search <pkg>` — search for a package in nixpkgs
* `syd isinstalled <pkg>` — check if package is listed or not
* `syd list` — print and count the number of installed packages
* `syd --reset` — reset your stored config path and rebuild command
* `syd --help` — show usage info

The config is stored in `~/.config/syd/config`, which remembers:

* your Nix packages file path (e.g. `/etc/nixos/packages.nix`)
* your rebuild command (e.g. `sudo nixos-rebuild switch`)

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

If you haven’t modularized your Nix config yet, create a separate file to handle packages — for example `packages.nix`.

Update your `configuration.nix` like this:

```nix
environment.systemPackages = import ./packages/packages.nix pkgs;
```

and structure your new file like:

```nix
{ pkgs }: with pkgs; [
  vim
  wget
  git
  # more packages...
]
```

Now **syd** can manage this file automatically.

---

## Notes

* syd was originally written in bash but is now entirely in **Python 3**, making it a lot faster.
* It expects a single `packages.nix` file by default, but you can adapt it for your own layout.
For reference, see [my NixOS setup](https://github.com/sidharthify/nixos-configs) to understand how I structure my configs. (not the best, I'm aware)

* An overview of syd's code can be found on [this blog](https://sidharthify.me/blogs/blog-18-10-25).
