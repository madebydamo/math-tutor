# Hermes skill for the Mathe-Trainer.
{...}: {
  neoPlugin.modules.mathtutor-skills = {
    config,
    lib,
    plugin,
    ...
  }: let
    name = plugin.name "mathtutor";
    cfg = config.neo.services.${name};
  in {
    config.neo.services.${name}.skill.conf = lib.neo.mkServiceSkill {
      service = name;
      inherit config;
      description = "Mathe-Trainer: maths coach app with AI tutor (Claude Code)";
      tags = ["neo" "mathtutor" "learning"];
      title = "Neo · Mathe-Trainer${plugin.label}";
      body = ''
        ## When to Use
        The maths coach site is down, the tutor does not answer, or the coach asks how the student is doing.

        ## Architecture notes
        - Web app container `${name}` (port ${toString cfg.port}) on `internal` and `${name}-sandbox`; SQLite + photos in appdata `app/`
        - Tutor container `${name}-agent` (port ${toString cfg.agentPort}) only on `${name}-sandbox`; runs `claude -p` per message with math MCP tools; HOME in appdata `agent/home`
        - Image built by the plugin, loaded by `${name}-image`
        - Identity comes from tinyauth (`Remote-User`): `services.${name}.studentUser` is the student, `services.${name}.adminUsers` see /admin
        - Progress API for the coach: `GET /api/admin/overview`, `/api/admin/struggles`, `/api/admin/briefing` (needs a coach login)

        ## Procedures
        1. `systemctl status ${name}-image docker-${name} docker-${name}-agent`
        2. `docker logs ${name} --tail 100`, `docker logs ${name}-agent --tail 100`
        3. Tutor auth check: `docker exec ${name} python -c "import urllib.request as u; print(u.urlopen('http://${name}-agent:${toString cfg.agentPort}/health').read())"` → `"auth": true`
        4. Tutor not signed in: set `services.${name}.claudeToken` (from `claude setup-token`) or `services.${name}.anthropicApiKey`, or run `docker exec -it ${name}-agent claude` and `/login`

        ## Credentials
        - `services.${name}.claudeToken`, `services.${name}.anthropicApiKey`, `services.${name}.agentToken`, `services.${name}.telegramBotToken`

        ## Verification
        - `GET https://<subdomain>.<domain>/health` returns 200 with the exercise count
        - `GET /` returns 302 to tinyauth
      '';
    };
  };
}
