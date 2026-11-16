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
        - Web app container `${name}` (port ${toString cfg.port}) on its service network `app-${name}` and `${name}-sandbox`; SQLite + photos in appdata `app/`
        - Tutor container `${name}-agent` (port ${toString cfg.agentPort}) only on `${name}-sandbox`; runs `claude -p` per message with math MCP tools (no network for the tools); HOME in appdata `agent/home`
        - The app trusts the login (`Remote-User`) only on requests from SWAG (header `X-Neo-Proxy-Secret`); direct calls are anonymous (401)
        - Image built by the plugin, loaded by `${name}-image`
        - Identity comes from tinyauth (`Remote-User`): `services.${name}.studentUser` is the student, `services.${name}.adminUsers` see /admin
        - Progress API for the coach: `GET /api/admin/overview`, `/api/admin/struggles`, `/api/admin/briefing` (needs a coach login through the website)
        - Logs are JSON lines with `level`; tutor turns log `event=tutor_turn` (feature, status, seconds, cost), exam grading `job=grading`, Telegram failures `event=telegram_failed`
        - With monitoring on: Grafana dashboard "Mathe-Trainer${plugin.label}" (Apps folder); metrics on `${name}:9464/metrics` (`mathtutor_*`, `neo_app_*`)

        ## Procedures
        1. `systemctl status ${name}-image docker-${name} docker-${name}-agent`
        2. `docker logs ${name} --tail 100`, `docker logs ${name}-agent --tail 100`
        3. Tutor auth check: `docker exec ${name} python -c "import urllib.request as u; print(u.urlopen('http://${name}-agent:${toString cfg.agentPort}/health').read())"` → `"auth": true`
        4. Tutor not signed in: set `services.${name}.claudeToken` (from `claude setup-token`) or `services.${name}.anthropicApiKey`, or run `docker exec -it ${name}-agent claude` and `/login`
        5. Errors only: `docker logs ${name} 2>&1 | grep -E '"level": "(error|critical)"' | tail -20` (same for `${name}-agent`); in Grafana/Loki `{unit=~"docker-${name}(-agent)?.service"} | json | level="error"`
        6. Exam grading stuck or failed: `docker exec ${name} python -c "import urllib.request as u; print(u.urlopen('http://localhost:9464/metrics').read().decode())" | grep -E 'gradings_pending|job_runs_total.*grading'` (needs monitoring on); a restart re-queues pending gradings

        ## Credentials
        - `services.${name}.claudeToken`, `services.${name}.anthropicApiKey`, `services.${name}.agentToken`, `services.${name}.telegramBotToken`

        ## Verification
        - `GET https://<subdomain>.<domain>/health` returns 200 with the exercise count
        - `GET /` returns 302 to tinyauth
      '';
    };
  };
}
