# SPDX-FileCopyrightText: © 2026 Alexander Kromm <mmaulwurff@gmail.com>
# SPDX-License-Identifier: CC0-1.0

# nixos-25.11:
# Emacs: 30.2
# GZDoom: 4.14.2
let
  nixpkgs = fetchTarball "https://github.com/NixOS/nixpkgs/archive/2c3e5ec5df46d3aeee2a1da0bfedd74e21f4bf3a.tar.gz";
  pkgs = import nixpkgs { config = {}; overlays = []; };
in

pkgs.mkShellNoCC {
  packages = with pkgs; [
    emacs-nox
    gzdoom
  ];

  shellHook = ''
    which emacs
    which emacs-nox
  '';

  NO_AT_BRIDGE = "1";
}
