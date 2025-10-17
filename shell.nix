{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "syd";

  buildInputs = with pkgs; [
    python3
    python3Packages.colorama
    python3Packages.flake8
    python3Packages.setuptools
    python3Packages.wheel
  ];

  shellHook = ''
    echo "Python shell loaded"
    echo "Run 'python syd.py' to test"
  '';
}