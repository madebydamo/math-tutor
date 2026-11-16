# The Mathe-Trainer app (Python/FastAPI + SymPy) and its OCI image (nix2container).
# One image runs both containers: the web app (MT_ROLE=app) and the isolated tutor
# agent (MT_ROLE=agent, Claude Code + math tools). The tag is the image's Nix hash.
{inputs, ...}: {
  perSystem = {
    system,
    lib,
    ...
  }: let
    # claude-code is unfree; allow exactly that package.
    pkgs = import inputs.nixpkgs {
      inherit system;
      config.allowUnfreePredicate = p: builtins.elem (lib.getName p) ["claude-code"];
    };
    # claude-code from nixos-unstable: the API rejects current models from older
    # Claude Code releases (e.g. claude-opus-5-5 needs >= 2.1.280, 26.05 has 2.1.223).
    pkgsUnstable = import inputs.nixpkgs-unstable {
      inherit system;
      config.allowUnfreePredicate = p: builtins.elem (lib.getName p) ["claude-code"];
    };
    inherit (pkgsUnstable) claude-code;
    n2c = inputs.nix2container.packages.${system}.nix2container;

    python = pkgs.python3.withPackages (p:
      with p; [
        fastapi
        uvicorn
        httpx
        python-multipart
        pillow
        mcp
        sympy
        numpy
        scipy
        matplotlib
        prometheus-client
      ]);

    # App source and course content, without dev leftovers.
    app = pkgs.runCommand "mathtutor-app" {} ''
      mkdir -p $out/app
      cp -r ${../app/mathtutor} $out/app/mathtutor
      cp -r ${../content} $out/app/content
      chmod -R u+w $out/app
      find $out/app -name '__pycache__' -prune -exec rm -rf {} +
      rm -rf $out/app/content/tools
    '';

    entrypoint = pkgs.writeShellScriptBin "mathtutor-entrypoint" ''
      set -eu
      export PYTHONPATH=/app
      mkdir -p "''${HOME:-/data/home}" 2>/dev/null || true
      case "''${MT_ROLE:-app}" in
        agent) exec ${python}/bin/python -m mathtutor.agent_server ;;
        *) exec ${python}/bin/python -m mathtutor.main ;;
      esac
    '';

    tools = pkgs.buildEnv {
      name = "mathtutor-tools";
      paths = with pkgs; [bashInteractive coreutils findutils gnugrep gnused cacert tzdata claude-code python entrypoint];
      pathsToLink = ["/bin" "/etc" "/share"];
    };

    # Kept apart from `root`: /etc also comes from `tools`, and nix2container refuses
    # a directory that two copyToRoot paths give different perms.
    etc = pkgs.runCommand "mathtutor-etc" {} ''
      mkdir -p $out/etc
      printf 'root:x:0:0:root:/root:/bin/sh\ntutor:x:1000:100::/data/home:/bin/sh\n' > $out/etc/passwd
      printf 'root:x:0:\nusers:x:100:\n' > $out/etc/group
    '';

    root = pkgs.runCommand "mathtutor-root" {} ''
      mkdir -p $out/tmp $out/data
    '';

    image = n2c.buildImage {
      name = "mathtutor";
      copyToRoot = [tools etc app root];
      layers = [(n2c.buildLayer {deps = [tools];})];
      perms = [
        {
          path = root;
          regex = "/tmp";
          mode = "1777";
        }
        {
          path = root;
          regex = "/data";
          mode = "0777";
        }
      ];
      config = {
        Entrypoint = ["/bin/mathtutor-entrypoint"];
        WorkingDir = "/app";
        Env = [
          "PATH=/bin"
          "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
          "MT_CONTENT_DIR=/app/content"
          "MT_STATIC_DIR=/app/mathtutor/static"
          "MT_CLAUDE_BIN=/bin/claude"
          "HOME=/data/home"
          "TZDIR=/share/zoneinfo"
        ];
      };
    };
  in {
    packages = {
      mathtutor-python = python;
      mathtutor-image = image;
    };
  };
}
