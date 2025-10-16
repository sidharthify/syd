# syd
**syd** (taken from **Syd Barrett**) is a way to install packages in NixOS like how you'd do in other major linux distributions. It appends package names to your nix file automatically, so you don’t have to open and edit it every time you want to install something. It basically acts like a lightweight package manager wrapper for any distro that manages packages through editable config files instead of commands.

---

## Usage
- `syd <pkg>` adds one or more packages to your saved config file
- `syd remove <pkg>` removes one or more packages to your saved config file
- `syd search <pkg>` searches for the package in nixpkgs
- `syd list` prints and counts the number of installed packages
- `syd --reset` clears the saved path
- `syd --help` shows usage info

This script stores your package directory and your rebuild command inside `~/.config/syd/config`

---

## Adapt to your setup
It’s recommended to create a separate Nix file to manage your packages if you haven’t already.

If your setup currently keeps everything inside `configuration.nix`, you’ll want to modularize it by creating a new file, for example `packages.nix`, to handle your package definitions.

Some users split their package definitions into multiple files, but for now, **syd** expects a single file path to work with. You can fork it later and extend the logic to support multiple files if you’d like.

To get started:
- Inside your NixOS configuration directory, open `configuration.nix`
- Cut the section where your packages are defined and paste it into a new file.
- Add this line to your `configuration.nix`:

```bash
environment.systemPackages = import ./packages/packages.nix pkgs;
```

**(make sure the path matches your directory structure)**

- Structure your new file like this:

```bash
{ pkgs }: with pkgs; [
  yad
  vim
  sudo
  # ...more packages
]
```

Once that’s done, rebuild your system and you’re ready to start using **syd**.

## Things to consider
- This isn't the best written script out there. It is written to suit my own nixOS setup, so you may fork it and make your own changes in the way that it is written. You may not even have a different `package.nix` file like I do - and just have a single `configuration.nix`, so for you, this script might not work - unless you do a few changes here and there. If you do want to see how my own `package.nix` is structured, head over to [my NixOS setup](https://github.com/sidharthify/nixos-configs). You may find it in `packages/packages.nix`

- I will keep updating this overtime, so one day, this may actually become quite a mature tool. But for now, use it if you REALLY want to.
