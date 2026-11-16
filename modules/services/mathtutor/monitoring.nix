# Mathe-Trainer metrics, dashboard and alert rules (Neo app telemetry, $NEO/docs/APP-TELEMETRY.md).
#
# The web app serves /metrics on :9464 (NEO_METRICS_PORT, only while a monitoring agent
# runs here), on its service network; never proxied. The agent container has no
# endpoint: each tutor turn's Claude Code usage and cost come back in its `done` line and
# the app counts them (neo_app_llm_*, provider claude_code).
# Metric names: app/mathtutor/metrics.py (features, jobs and app numbers listed there).
{...}: {
  neoPlugin.modules.mathtutor-monitoring = {
    config,
    lib,
    plugin,
    ...
  }: let
    name = plugin.name "mathtutor";
    agent = "${name}-agent";
    cfg = config.neo.services.${name};
    label = "Mathe-Trainer${plugin.label}";
    sel = lib.neo.grafana.appSelector name;
    asel = lib.neo.grafana.alertSelector name;
    student = ''${sel}, role="student"'';

    steps = colors: {
      mode = "absolute";
      steps =
        map (c: {
          color = builtins.elemAt c 0;
          value = builtins.elemAt c 1;
        })
        colors;
    };
    redOrangeGreen = lo: hi: steps [["red" null] ["orange" lo] ["green" hi]];
    greenRed = steps [["green" null] ["red" 1]];
    yesNo = [
      {
        type = "value";
        options = {
          "0" = {
            text = "No";
            color = "red";
            index = 0;
          };
          "1" = {
            text = "Yes";
            color = "green";
            index = 1;
          };
        };
      }
    ];
  in {
    config = lib.mkIf cfg.enabled {
      virtualisation.oci-containers.containers.${name}.environment =
        lib.mkIf config.neo.monitoring.collecting {NEO_METRICS_PORT = "9464";};

      neo.monitoring.apps.${name} = {
        metrics.main = {
          container = name;
          port = 9464;
        };

        dashboards.overview = {
          title = label;
          description = "How the student is getting on before the exam, how well and at what cost the AI tutor works, and the app's errors.";
          time = "now-7d";
          panels = with lib.neo.grafana;
            [
              (row "Exam preparation" null)
              (stat {
                title = "Running";
                w = 3;
                h = 4;
                description = "The web app answers (the tutor container has its own panel: Tutor signed in).";
                targets = [(pq "min(up{${sel}})" "")];
                mappings = upDown;
                thresholds = steps [["red" null] ["green" 1]];
              })
              (stat {
                title = "Exam readiness";
                w = 4;
                h = 4;
                description = "Mastery of each chapter weighted by its points in past exams.";
                unit = "percentunit";
                decimals = 0;
                targets = [(pq "max(mathtutor_exam_readiness_ratio{${sel}})" "")];
                thresholds = redOrangeGreen 0.5 0.75;
              })
              (stat {
                title = "Right answers (7 days)";
                w = 4;
                h = 4;
                description = "Share of the student's answers in the last 7 days that were right.";
                unit = "percentunit";
                decimals = 0;
                targets = [(pq "max(mathtutor_accuracy_7d_ratio{${sel}})" "")];
                thresholds = redOrangeGreen 0.5 0.7;
                noValue = "no answers";
              })
              (stat {
                title = "Days to the exam";
                w = 3;
                h = 4;
                targets = [(pq "max(mathtutor_days_to_exam{${sel}})" "")];
                options.colorMode = "none";
              })
              (stat {
                title = "Days to the next session";
                w = 3;
                h = 4;
                targets = [(pq "max(mathtutor_days_to_session{${sel}})" "")];
                options.colorMode = "none";
                noValue = "none planned";
              })
              (stat {
                title = "Streak";
                w = 3;
                h = 4;
                description = "Days in a row the student practised.";
                unit = "d";
                targets = [(pq "max(mathtutor_streak_days{${sel}})" "")];
                options.colorMode = "none";
              })
              (stat {
                title = "Tutor signed in";
                w = 4;
                h = 4;
                description = "The tutor container has a Claude token or API key.";
                targets = [(pq "min(mathtutor_tutor_signed_in{${sel}})" "")];
                mappings = yesNo;
                thresholds = steps [["red" null] ["green" 1]];
                noValue = "unreachable";
              })
              (stat {
                title = "AI vs checker disagreements";
                w = 4;
                h = 4;
                description = "Photo corrections where the AI's verdict on a final answer differed from the SymPy checker (the checker wins). A rising number means the tutor reads or judges work badly.";
                decimals = 0;
                targets = [(pq "sum(increase(mathtutor_review_disagreements_total{${sel}}[$__range])) or vector(0)" "")];
                thresholds = steps [["green" null] ["orange" 1] ["red" 5]];
              })
              (stat {
                title = "Exam gradings waiting";
                w = 4;
                h = 4;
                description = "Photographed exam exercises the tutor has not graded yet.";
                targets = [(pq "max(mathtutor_exam_gradings_pending{${sel}})" "")];
                thresholds = greenRed;
              })
              (stat {
                title = "Last exam simulation";
                w = 4;
                h = 4;
                unit = "percentunit";
                decimals = 0;
                targets = [(pq "max(mathtutor_last_exam_score_ratio{${sel}})" "")];
                thresholds = redOrangeGreen 0.5 0.7;
                noValue = "none yet";
              })
              (stat {
                title = "Open reports";
                w = 4;
                h = 4;
                description = "Exercise error reports and feedback the coach has not handled.";
                targets = [
                  (pq "max(mathtutor_reports_open{${sel}})" "reports")
                  (pq "max(mathtutor_feedback_open{${sel}})" "feedback")
                ];
                options = {
                  colorMode = "none";
                  textMode = "value_and_name";
                };
              })
              (stat {
                title = "Topics mastered";
                w = 4;
                h = 4;
                targets = [(pq "max(mathtutor_skills_mastered{${sel}})" "")];
                options.colorMode = "none";
              })

              (row "Learning" null)
              (bars {
                title = "Answers per day";
                w = 12;
                h = 8;
                description = "The student's checked answers (typed and photo corrections), by result.";
                interval = "1d";
                targets = [(pq "sum by (result) (increase(mathtutor_answers_total{${student}}[$__interval]))" "{{result}}")];
              })
              (timeseries {
                title = "Readiness, mastery and right answers";
                w = 12;
                h = 8;
                unit = "percentunit";
                min = 0;
                max = 1;
                targets = [
                  (pq "max(mathtutor_exam_readiness_ratio{${sel}})" "exam readiness")
                  (pq "max(mathtutor_overall_mastery_ratio{${sel}})" "mastery")
                  (pq "max(mathtutor_accuracy_7d_ratio{${sel}})" "right answers (7 days)")
                ];
              })
              (bargauge {
                title = "Mastery per chapter";
                w = 8;
                h = 10;
                unit = "percentunit";
                min = 0;
                max = 1;
                targets = [(pq "max by (chapter) (mathtutor_chapter_mastery_ratio{${sel}})" "{{chapter}}")];
              })
              (bargauge {
                title = "Weakest topics";
                w = 8;
                h = 10;
                description = "Practised topics with the lowest mastery.";
                unit = "percentunit";
                min = 0;
                max = 1;
                targets = [(pq "bottomk(10, max by (skill) (mathtutor_skill_mastery_ratio{${sel}}))" "{{skill}}")];
              })
              (bargauge {
                title = "Mistake types";
                w = 8;
                h = 10;
                description = "Kinds of mistakes in the student's wrong answers in the chosen time range.";
                targets = [(pq "sort_desc(round(sum by (error_category) (increase(mathtutor_wrong_answers_total{${sel}}[$__range]))))" "{{error_category}}")];
              })
              (bars {
                title = "Practice minutes per day";
                w = 12;
                h = 8;
                interval = "1d";
                unit = "m";
                targets = [(pq ''sum(increase(mathtutor_practice_seconds_total{${sel}, role="student"}[$__interval])) / 60'' "minutes")];
              })
              (timeseries {
                title = "Revanche re-tests";
                w = 12;
                h = 8;
                description = "Exercises the student got wrong and must beat twice (open, due now, won).";
                targets = [(pq "max by (state) (mathtutor_challenges{${sel}})" "{{state}}")];
              })

              (row "AI tutor quality" null)
              (bars {
                title = "Disagreements by chapter";
                w = 8;
                h = 8;
                targets = [(pq "sum by (chapter) (increase(mathtutor_review_disagreements_total{${sel}}[$__interval]))" "{{chapter}}")];
              })
              (bars {
                title = "Photo corrections";
                w = 8;
                h = 8;
                description = "Corrections of handwritten work; \"none\" means the tutor handed in no result.";
                targets = [(pq "sum by (kind, outcome) (increase(mathtutor_reviews_total{${sel}}[$__interval]))" "{{kind}} {{outcome}}")];
              })
              (bars {
                title = "Maths tools used";
                w = 8;
                h = 8;
                targets = [(pq "sum by (tool) (increase(mathtutor_tutor_tool_calls_total{${sel}}[$__interval]))" "{{tool}}")];
              })
              (timeseries {
                title = "Time to the tutor's first words";
                w = 12;
                h = 8;
                unit = "s";
                targets = [
                  (pq "histogram_quantile(0.5, sum by (le) (rate(mathtutor_tutor_first_text_seconds_bucket{${sel}}[$__rate_interval])))" "median")
                  (pq "histogram_quantile(0.95, sum by (le) (rate(mathtutor_tutor_first_text_seconds_bucket{${sel}}[$__rate_interval])))" "95th percentile")
                ];
              })
              (timeseries {
                title = "Steps per tutor answer (95th percentile)";
                w = 12;
                h = 8;
                description = "Model steps the tutor needed per answer; 25 is the limit.";
                targets = [(pq "histogram_quantile(0.95, sum by (le, feature) (rate(mathtutor_tutor_turn_steps_bucket{${sel}}[$__rate_interval])))" "{{feature}}")];
              })
              (bars {
                title = "Telegram messages to the coach";
                w = 12;
                h = 8;
                targets = [(pq "sum by (result) (increase(mathtutor_telegram_messages_total{${sel}}[$__interval]))" "{{result}}")];
              })
              (timeseries {
                title = "Memory";
                w = 12;
                h = 8;
                unit = "bytes";
                description = "The tutor container is limited to 2 GiB.";
                targets = [(pq ''container_memory_working_set_bytes{host=~"$host", name=~"${name}|${agent}"}'' "{{name}}")];
              })
            ]
            ++ (with lib.neo.grafana.app;
              features {service = name;}
              ++ llm {
                service = name;
                title = "AI tutor (with a Claude token, cost is the API price equivalent)";
              }
              ++ jobs {service = name;}
              ++ web {service = name;}
              ++ errors {
                service = name;
                containers = [name agent];
              });
        };

        alerts =
          lib.neo.monitoring.appAlerts {
            service = name;
            inherit label;
            containers = [name agent];
            llm = true;
            # The notification loop ticks every 10 minutes.
            jobs.notifications = 2 * 3600;
          }
          // {
            # Grading only runs when an exam with photos is handed in, so its
            # failures fire (a last-success age would alert between exams).
            grading-failed = {
              title = "${label}: exam grading failed";
              expr = ''sum by (host) (increase(neo_app_job_runs_total{${asel}, job="grading", status="failure"}[1h]))'';
              above = 0;
              for = "0s";
              summary = "${label} could not grade {{ printf \"%.0f\" $values.B.Value }} photographed exam exercise(s) in the last hour; the exam page shows them as failed.";
            };
            grading-stuck = {
              title = "${label}: exam grading stuck";
              expr = ''max by (host) (mathtutor_exam_gradings_pending{${asel}})'';
              above = 0;
              for = "45m";
              summary = "${label} has had {{ printf \"%.0f\" $values.B.Value }} exam exercise(s) waiting for grading for 45 minutes.";
            };
            tutor-signed-out = {
              title = "${label}: tutor not signed in";
              expr = ''min by (host) (mathtutor_tutor_signed_in{${asel}})'';
              below = 1;
              for = "10m";
              severity = "critical";
              summary = "The AI tutor of ${label} has no Claude token or API key: set one in the service settings.";
            };
            telegram-failing = {
              title = "${label}: Telegram messages fail";
              expr = ''sum by (host) (increase(mathtutor_telegram_messages_total{${asel}, result!="ok"}[1h]))'';
              above = 0;
              for = "0s";
              summary = "${label} could not send {{ printf \"%.0f\" $values.B.Value }} Telegram message(s) to the coach in the last hour (bot token or chat ID wrong?).";
            };
            disagreements = {
              title = "${label}: AI and checker often disagree";
              expr = ''sum by (host) (increase(mathtutor_review_disagreements_total{${asel}}[1d]))'';
              above = 4;
              for = "0s";
              summary = "In {{ printf \"%.0f\" $values.B.Value }} photo corrections today the AI tutor judged a final answer differently from the checker: look at them on the coach page.";
            };
            no-practice = {
              title = "${label}: no practice for a week";
              expr = ''max by (host) (time() - mathtutor_last_practice_timestamp_seconds{${asel}}) and on (host) max by (host) (mathtutor_days_to_exam{${asel}}) < 60'';
              above = 7 * 86400;
              for = "1h";
              severity = "info";
              summary = "The student has not practised for {{ humanizeDuration $values.B.Value }}, and the exam is less than two months away.";
            };
          };
      };
    };
  };
}
