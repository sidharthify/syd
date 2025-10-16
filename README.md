# nixstall
Nixstall is a way to install packages in NixOS like how you'd do in other major linux distributions. It appends package names to your nix file automatically, so you don’t have to open and edit it every time you want to install something. It basically acts like a lightweight package manager wrapper for any distro that manages packages through editable config files instead of commands.

---

## Usage
```bash
nixstall <package> [more packages]
nixstall --reset
nixstall --help
```

- `nixstall <pkg>` adds one or more packages to your saved config file
- `nixstall --reset` clears the saved path
- `nixstall --help` shows usage info

This script stores your package directory and your rebuild command inside `~/.config/nixstall/config`

---

## Things to consider
- This isn't the best written script out there. It is written to suit my own nixOS setup, so you may fork it and make your own changes in the way that it is written. You may not even have a different `package.nix` file like I do - and just have a single `configuration.nix`, so for you, this script might not work - unless you do a few changes here and there. If you do want to see how my own `package.nix` is structured, head over to [my NixOS setup](https://github.com/sidharthify/nixos-configs). You may find it in `packages/packages.nix`

- I will keep updating this overtime, so one day, this may actually become quite a mature tool. But for now, use it if you REALLY want to.
