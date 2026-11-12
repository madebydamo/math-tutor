# Options of the Mathe-Trainer: a personal maths coach (Mathematik II, HF) with an AI tutor.
# Two containers from one self-built image: the web app (`<name>`) and the tutor agent
# (`<name>-agent`, Claude Code with math tools on its own network, no access to other services).
{withSystem, ...}: {
  neoPlugin.modules.mathtutor-option = {
    config,
    lib,
    pkgs,
    plugin,
    ...
  }:
    with lib;
    with {inherit (lib.neo) mkOption mkEnableOption;}; let
      name = plugin.name "mathtutor";
      image = withSystem pkgs.stdenv.hostPlatform.system ({config, ...}: config.packages.mathtutor-image);
      tag = "${name}:${builtins.unsafeDiscardStringContext image.imageTag}";
      tutorGroup = lib.neo.ui.mkGroup {
        id = "tutor";
        label = "AI tutor";
        rank = 40;
      };
      notifyGroup = lib.neo.ui.mkGroup {
        id = "notify";
        label = "Telegram";
        rank = 60;
      };
    in {
      options.neo.services.${name} = mkOption {
        type = types.submodule {
          options =
            {
              enabled = mkEnableOption "A personal maths coach with exercises, progress tracking and an AI tutor${plugin.label}" {rank = 0;};

              port = mkOption {
                type = types.port;
                internal = true;
                default = 8080;
                description = "Port of the web app inside the container";
              };
              agentPort = mkOption {
                type = types.port;
                internal = true;
                default = 8100;
                description = "Port of the tutor agent inside its container";
              };

              studentUser = mkOption {
                type = types.nullOr types.str;
                default = null;
                rank = 10;
                description = "Login name of the student (as in the login page users). Only this person's work counts for the progress overview.";
                ui = lib.neo.ui.mkUi {label = "Student login";};
              };
              studentName = mkOption {
                type = types.str;
                default = "";
                rank = 11;
                description = "First name the app and the tutor use for the student. Empty uses the login name.";
                ui = lib.neo.ui.mkUi {label = "Student name";};
              };
              adminUsers = mkOption {
                type = types.listOf types.str;
                default = [];
                rank = 12;
                description = "Login names of the coaches. They see the coach dashboard; their own practice never counts as the student's.";
                ui = lib.neo.ui.mkUi {label = "Coach logins";};
              };

              # CLAUDE_CODE_OAUTH_TOKEN for the agent container (from `claude setup-token`).
              claudeToken = lib.neo.mkSecretOption {
                type = types.nullOr types.str;
                default = null;
                rank = 41;
                description = "Sign-in token for your Claude subscription, created with «claude setup-token» on any computer. Leave empty if you use an API key instead.";
                ui = lib.neo.ui.mkUi {
                  label = "Claude token";
                  group = tutorGroup;
                };
              };
              # ANTHROPIC_API_KEY for the agent container (pay per use instead of a subscription).
              anthropicApiKey = lib.neo.mkSecretOption {
                type = types.nullOr types.str;
                default = null;
                rank = 42;
                description = "Anthropic API key, as an alternative to the Claude token. Usage is billed to that API account.";
                ui = lib.neo.ui.mkUi {
                  label = "Anthropic API key";
                  group = tutorGroup;
                };
              };
              model = mkOption {
                type = types.str;
                default = "claude-opus-5-5";
                rank = 43;
                description = "The Claude model the tutor thinks with. The most capable model makes the fewest mistakes.";
                ui = lib.neo.ui.mkUi {
                  label = "Tutor model";
                  group = tutorGroup;
                };
              };
              # Shared secret between the web app and the agent container.
              agentToken = lib.neo.mkSecretOption {
                type = types.nullOr types.str;
                default = null;
                rank = 44;
                description = "Internal password between the app and its tutor. Generate it once; changing it later needs no other step.";
                helper = lib.neo.helpers.randomToken;
                ui = lib.neo.ui.mkUi {
                  label = "Tutor connection secret";
                  group = tutorGroup;
                };
              };

              telegramBotToken = lib.neo.mkSecretOption {
                type = types.nullOr types.str;
                default = null;
                rank = 61;
                description = "Telegram bot for the coach's daily summary and alerts. Empty uses the Hermes bot, if Hermes has one.";
                ui = lib.neo.ui.mkUi {
                  label = "Telegram bot token";
                  group = notifyGroup;
                };
              };
              telegramChatId = mkOption {
                type = types.str;
                default = "";
                rank = 62;
                description = "Your Telegram chat ID for the coach messages. Empty uses the first Hermes Telegram user.";
                ui = lib.neo.ui.mkUi {
                  label = "Telegram chat ID";
                  group = notifyGroup;
                };
              };
            }
            // lib.neo.mkReverseProxyOptions {
              subdomain = plugin.name "mathe";
              auth.publicPaths = ["^/health$"];
            }
            // lib.neo.mkContainerDefinitions {
              ${name} = tag;
              "${name}-agent" = tag;
              extraUnits = ["${name}-image"];
            }
            // lib.neo.mkAppdata "${config.neo.core.volumes.appdata}/${name}"
            // lib.neo.mkServiceMeta {
              category = "Other";
              icon = ./icon.svg;
              tagline = "A personal maths coach with an AI tutor${plugin.label}";
              description = ''
                Exercises from the course with step-by-step help, photo correction of handwritten work,
                ranks and daily missions, and a coach dashboard that shows exactly where the student struggles.
              '';
              notes = ''
                The tutor runs Claude Code in its own container, with only maths tools and no access to your other services.
                Sign it in with a Claude token («claude setup-token») or an API key.
                Coaches open /admin. Practice of a coach is never counted as the student's.
                Exercises, theory and the formula sheet ship with the plugin; progress lives in appdata.
              '';
              replaces = ["Private tutoring apps"];
              privacy = ["assistant"];
              projectUrl = "https://github.com/madebydamo";
              license = {
                spdx = "MIT";
                url = "https://opensource.org/license/mit";
                openSource = false;
                note = "The AI tutor uses Claude Code and Anthropic's servers (closed). Everything else is open source.";
              };
            }
            // lib.neo.mkSkillOptions {};
        };
        default = {};
        description = "Mathe-Trainer";
      };
    };
}
