{
  description = "syd - a lightweight declarative Nix helper for NixOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      packages.${system}.default = pkgs.stdenv.mkDerivation {
        pname = "syd";
        version = "2.0";

        src = ./.;

        buildInputs = [
          (pkgs.python3.withPackages (ps: with ps; [
            colorama
        ]))
        pkgs.makeWrapper
      ];


        installPhase = ''
          mkdir -p $out/bin
          cp syd.py $out/bin/syd
          chmod +x $out/bin/syd

          wrapProgram $out/bin/syd \
            --set PATH ${pkgs.python3}/bin:$PATH
        '';
      };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/syd";
      };

      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs.python3Packages; [
          colorama
          flake8
          setuptools
          wheel
        ];
      };
    };
}