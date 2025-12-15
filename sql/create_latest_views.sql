CREATE OR replace VIEW latest.migrants_arrived_weekly AS (
       SELECT
         record_id,
         week_ending,
         migrants_arrived,
         boats_arrived,
         boats_arrived_involved_in_uncontrolled_landings,
         migrants_prevented,
         events_prevented,
         notes
       FROM raw.migrants_arrived_weekly
       WHERE is_current = TRUE
       ORDER BY week_ending DESC
);

CREATE OR REPLACE VIEW latest.migrants_arrived_daily as (
       select
         record_id,
         day_ending,
         migrants_arrived,
         boats_arrived,
         boats_arrived_involved_in_uncontrolled_landings,
         notes
       FROM raw.migrants_arrived_daily
       WHERE is_current = TRUE
       ORDER BY day_ending DESC
);