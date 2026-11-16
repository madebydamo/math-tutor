# Mathe-Trainer implementation.
# - `<name>-image` loads the Nix-built image under this copy's name.
# - `<name>`: web app on its service network `app-<name>` (SWAG, metrics) and on
#   `<name>-sandbox` (to reach the agent).
# - `<name>-agent`: Claude Code + math tools, only on `<name>-sandbox` (internet for
#   Anthropic, no route to other services). Its maths tools run without any network
#   (seccomp, app/mathtutor/sandbox.py).
# Neo creates both networks from the containers' `networks` and removes them when the
# service is off. The app trusts `Remote-User` only on requests that carry SWAG's
# X-Neo-Proxy-Secret (generated secret `<name>-proxy`, see swag.nix), so the agent
# cannot pass as a user by calling the app directly.
{withSystem, ...}: {
  neoPlugin.modules.mathtutor = {
    config,
    lib,
    pkgs,
    plugin,
    ...
  }:
    with lib; let
      name = plugin.name "mathtutor";
      agent = "${name}-agent";
      sandbox = "${name}-sandbox";
      cfg = config.neo.services.${name};
      appdata = "${config.neo.core.volumes.appdata}/${name}";
      image = withSystem pkgs.stdenv.hostPlatform.system ({config, ...}: config.packages.mathtutor-image);
      docker = "${config.virtualisation.docker.package}/bin/docker";
      localRef = "${name}:${image.imageTag}";
      publicUrl = lib.neo.publicUrl config cfg;
      hermes = config.neo.services.hermes or {};
      tgToken =
        if lib.neo.isSet cfg.telegramBotToken
        then cfg.telegramBotToken
        else (hermes.telegramBotToken or null);
      tgChat =
        if cfg.telegramChatId != ""
        then cfg.telegramChatId
        else (let ids = hermes.telegramAllowedUserId or []; in optionalString (ids != []) (toString (head ids)));
      user = "${toString config.neo.core.uid}:${toString config.neo.core.gid}";
    in {
      config = mkIf cfg.enabled {
        assertions =
          [
            {
              assertion = lib.neo.isSet cfg.studentUser;
              message = "neo.services.${name}: set studentUser (the student's login name).";
            }
          ]
          ++ lib.neo.requireSecrets name cfg [
            {
              name = "agentToken";
              minLength = 16;
            }
          ];

        warnings =
          optional (!(lib.neo.isSet cfg.claudeToken) && !(lib.neo.isSet cfg.anthropicApiKey))
          "neo.services.${name}: neither claudeToken nor anthropicApiKey is set; the tutor only works after an interactive login (docker exec -it ${agent} claude, then /login).";

        systemd.services."${name}-image" = {
          description = "Load the Mathe-Trainer image";
          after = ["docker.service" "docker.socket"];
          requires = ["docker.service"];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = ''
            if ! ${docker} image inspect ${localRef} >/dev/null 2>&1; then
              ${image.copyTo}/bin/copy-to docker-daemon:${localRef}
            fi
            ${docker} image ls ${name} --format '{{.Repository}}:{{.Tag}}' \
              | grep -vxF ${localRef} \
              | xargs -r ${docker} rmi 2>/dev/null || true
          '';
        };

        systemd.services."docker-${name}" = {
          requires = ["${name}-image.service"];
          after = ["${name}-image.service"];
          preStart = lib.neo.mkEnsureDirs config [appdata "${appdata}/app" "${appdata}/agent" "${appdata}/agent/home"];
        };
        systemd.services."docker-${agent}" = {
          requires = ["${name}-image.service"];
          after = ["${name}-image.service"];
          preStart = lib.neo.mkEnsureDirs config [appdata "${appdata}/agent" "${appdata}/agent/home"];
        };

        virtualisation.oci-containers.containers.${name} = {
          image = cfg.containers.${name};
          environment = {
            MT_ROLE = "app";
            MT_DATA_DIR = "/data";
            MT_PORT = toString cfg.port;
            MT_AGENT_URL = "http://${agent}:${toString cfg.agentPort}";
            MT_STUDENT_USER =
              if cfg.studentUser == null
              then ""
              else cfg.studentUser;
            MT_STUDENT_NAME = cfg.studentName;
            MT_ADMIN_USERS = concatStringsSep "," cfg.adminUsers;
            MT_MODEL = cfg.model;
            MT_TELEGRAM_CHAT = tgChat;
            MT_PUBLIC_URL =
              if publicUrl == null
              then ""
              else publicUrl;
            TZ = config.neo.core.timeZone;
          };
          volumes = ["${appdata}/app:/data"];
          # Service network first: SWAG and the metrics scrape use it.
          networks = [(lib.neo.docker.serviceNetwork name) sandbox];
          extraOptions = ["--user=${user}"];
          dependsOn = [agent];
        };

        virtualisation.oci-containers.containers.${agent} = {
          image = cfg.containers.${agent};
          environment = {
            MT_ROLE = "agent";
            MT_AGENT_PORT = toString cfg.agentPort;
            MT_AGENT_WORK = "/tmp/mt-agent";
            HOME = "/data/home";
            TZ = config.neo.core.timeZone;
          };
          volumes = ["${appdata}/agent:/data"];
          networks = [sandbox];
          extraOptions = ["--user=${user}" "--memory=2g" "--pids-limit=512"];
        };

        # Sent by SWAG with every proxied request (swag.nix); generated on the machine.
        neo.core.secrets.generated."${name}-proxy" = {};

        neo.core.secrets.containerEnv = {
          ${name} =
            {
              MT_AGENT_TOKEN = cfg.agentToken;
              NEO_PROXY_SECRET = lib.neo.secrets.mkPlaceholder "generated/${name}-proxy";
            }
            // optionalAttrs (tgToken != null && tgToken != "") {MT_TELEGRAM_TOKEN = tgToken;};
          ${agent} =
            {MT_AGENT_TOKEN = cfg.agentToken;}
            // optionalAttrs (lib.neo.isSet cfg.claudeToken) {CLAUDE_CODE_OAUTH_TOKEN = cfg.claudeToken;}
            // optionalAttrs (lib.neo.isSet cfg.anthropicApiKey) {ANTHROPIC_API_KEY = cfg.anthropicApiKey;};
        };
      };
    };
}
