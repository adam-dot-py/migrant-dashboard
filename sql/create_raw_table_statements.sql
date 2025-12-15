create or replace table raw.migrants_arrived_weekly (
    week_ending DATE,
    migrants_arrived INT,
    boats_arrived INT,
    boats_arrived_involved_in_uncontrolled_landings INT,
    migrants_prevented INT,
    events_prevented INT,
    notes VARCHAR,
    is_current BOOLEAN,
    begin_date DATE,
    end_date DATE
 );

 create or replace table raw.migrants_arrived_daily (
    record_id BIGINT,
    day_ending DATE,
    migrants_arrived INT,
    boats_arrived INT,
    boats_arrived_involved_in_uncontrolled_landings INT,
    notes VARCHAR,
    is_current BOOLEAN,
    begin_date DATE,
    end_date DATE
 );