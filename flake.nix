{
  description = "syd";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      packages.${system}.default = pkgs.stdenv.mkDerivation {
        pname = "syd";
        version = "1.0";
        src = ./.;
        buildInputs = [ pkgs.zsh ];

        installPhase = ''
          mkdir -p $out/bin
          cp syd.sh $out/bin/syd
          chmod +x $out/bin/syd
        '';
      };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/syd";
      };
    };
}
