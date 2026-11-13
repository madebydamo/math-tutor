# Inputs for flake.nix (regenerate it with `nix run .#write-flake`).
# A homeserver adds this plugin with neo, nixpkgs and flake-file following its own
# inputs, so these URLs only matter when the plugin is evaluated on its own.
{...}: {
  flake-file.inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    # Only for claude-code: new models need a newer Claude Code than stable ships.
    # Deliberately not followed by the host, or the tutor falls back to stable's version.
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    neo.url = "github:madebydamo/neo";
    neo.inputs.nixpkgs.follows = "nixpkgs";
    nix2container.url = "github:nlewo/nix2container";
    nix2container.inputs.nixpkgs.follows = "nixpkgs";
  };
}
