-- CandyOps dashboard datasets (Databricks AI/BI dashboard -> Data -> "Create from SQL", one query each)
-- SYNTHETIC DATA. All values are modeled outcomes of a rule-based simulation, not observed results.
-- Tables live in workspace.candyops. If you used another catalog/schema, find-and-replace
-- "workspace.candyops." below before pasting.
-- "Ready to ship" = finished bags allocated at the dispatch factory by the end of the deadline day.
-- It is NOT customer delivery performance.


-- ds01_scenario_kpis : on-time ready-to-ship rate, cost and constraint per scenario (counters + bar charts)
SELECT
  scenario_id,
  scenario_name,
  scenario_kind,
  orders_total,
  orders_fully_ready,
  bags_ordered,
  bags_ready_on_time,
  bags_short,
  ROUND(on_time_ready_rate_bags * 100, 1)          AS on_time_ready_pct,
  ROUND(affected_factory_ready_rate_bags * 100, 1) AS northfield_ready_pct,
  incremental_cost_usd,
  overtime_cost_usd,
  alternate_run_cost_usd,
  transfer_freight_usd,
  incremental_ready_bags_vs_s1,
  cost_per_incremental_ready_bag_usd,
  primary_constraint,
  constraint_detail
FROM workspace.candyops.gold_scenario_summary
ORDER BY scenario_id;


-- ds01b_kpi_tiles : one-row values for the headline counters (no widget filter needed)
SELECT
  MAX(CASE WHEN scenario_id = 'S0_REFERENCE_NO_BREAKDOWN' THEN ROUND(on_time_ready_rate_bags * 100, 1) END) AS reference_ready_pct,
  MAX(CASE WHEN scenario_id = 'S1_NO_RECOVERY' THEN ROUND(on_time_ready_rate_bags * 100, 1) END)          AS no_recovery_ready_pct,
  MAX(CASE WHEN scenario_id = 'S2_OVERTIME' THEN ROUND(on_time_ready_rate_bags * 100, 1) END)             AS overtime_ready_pct,
  MAX(CASE WHEN scenario_id = 'S3_TRANSFER' THEN ROUND(on_time_ready_rate_bags * 100, 1) END)             AS transfer_ready_pct,
  MAX(CASE WHEN scenario_id = 'S4_OVERTIME_AND_TRANSFER' THEN ROUND(on_time_ready_rate_bags * 100, 1) END) AS combined_ready_pct,
  MAX(CASE WHEN scenario_id = 'S1_NO_RECOVERY' THEN bags_short END)                                       AS bags_short_no_recovery
FROM workspace.candyops.gold_scenario_summary;


-- ds02_orders_at_risk : orders the breakdown puts at risk (ready in S0 reference, not in S1)
SELECT
  o.order_id,
  o.customer_name,
  o.sku_id,
  o.ready_to_ship_deadline,
  o.order_qty_bags,
  o.ready_on_time_bags                          AS ready_bags_no_recovery,
  o.short_bags                                  AS short_bags_no_recovery,
  o.short_value_usd                             AS modeled_wholesale_value_short_usd
FROM workspace.candyops.gold_order_fulfillment o
WHERE o.scenario_id = 'S1_NO_RECOVERY' AND o.at_risk_after_breakdown
ORDER BY o.ready_to_ship_deadline, o.order_id;


-- ds03_order_fulfillment : every order x scenario (table / heatmap; filter on scenario_id)
SELECT
  scenario_id,
  order_id,
  customer_name,
  dispatch_factory_id,
  sku_id,
  ready_to_ship_deadline,
  order_qty_bags,
  ready_on_time_bags,
  short_bags,
  ROUND(ready_on_time_pct * 100, 1) AS ready_on_time_pct,
  status,
  at_risk_after_breakdown
FROM workspace.candyops.gold_order_fulfillment
ORDER BY scenario_id, ready_to_ship_deadline, order_id;


-- ds04_production_vs_plan : daily planned vs good output per factory (filter on scenario_id)
SELECT
  scenario_id,
  `date`,
  factory_id,
  line_id,
  run_type,
  SUM(planned_bags)        AS planned_bags,
  SUM(total_bags)          AS total_bags,
  SUM(good_bags)           AS good_bags,
  SUM(lost_equipment_bags) AS lost_to_equipment_bags,
  SUM(lost_material_bags)  AS lost_to_material_bags
FROM workspace.candyops.gold_daily_line_production
GROUP BY scenario_id, `date`, factory_id, line_id, run_type
ORDER BY scenario_id, `date`, line_id, run_type;


-- ds05_runtime_downtime : line-hours per line-day (stacked bar; filter on scenario_id)
SELECT
  scenario_id,
  `date`,
  line_id,
  planned_operating_hours,
  downtime_hours,
  runtime_standard_hours,
  runtime_overtime_hours,
  idle_standard_hours,
  CASE WHEN scheduled_standard_hours > 0
       THEN ROUND(runtime_standard_hours / scheduled_standard_hours * 100, 1) END AS availability_pct
FROM workspace.candyops.gold_daily_line_capacity
ORDER BY scenario_id, `date`, line_id;


-- ds06_quality : yield and scrap per scenario and line (zero-safe)
SELECT
  scenario_id,
  line_id,
  SUM(total_bags)  AS total_bags,
  SUM(good_bags)   AS good_bags,
  SUM(reject_bags) AS reject_bags,
  CASE WHEN SUM(total_bags) > 0 THEN ROUND(SUM(good_bags) / SUM(total_bags) * 100, 2) END AS quality_yield_pct,
  ROUND(SUM(scrap_kg), 1) AS scrap_kg
FROM workspace.candyops.gold_daily_line_production
GROUP BY scenario_id, line_id
ORDER BY scenario_id, line_id;


-- ds07_seasonal_packaging : Halloween film stock by day and factory (line chart; filter on scenario_id)
SELECT
  scenario_id,
  `date`,
  factory_id,
  material_id,
  opening_qty,
  receipts_qty,
  consumed_qty,
  closing_qty,
  requested_shortfall_qty
FROM workspace.candyops.gold_material_balance
WHERE category = 'seasonal_packaging'
ORDER BY scenario_id, factory_id, material_id, `date`;


-- ds08_spare_capacity : where spare line-hours did / did not become usable output
SELECT
  scenario_id,
  `date`,
  line_id,
  mode,
  spare_hours,
  recovery_hours_planned,
  recovery_runtime_hours,
  material_blocked_hours,
  unused_hours,
  status
FROM workspace.candyops.gold_recovery_capacity
WHERE spare_hours > 0 OR status LIKE 'unavailable%'
ORDER BY scenario_id, `date`, line_id;


-- ds09_halloween_inventory : seasonal finished goods left after Oct 31 (markdown is an ASSUMPTION)
SELECT
  scenario_id,
  factory_id,
  item_id            AS sku_id,
  remaining_qty      AS bags_remaining,
  in_transit_qty     AS bags_in_transit,
  std_cost_value_usd,
  assumed_markdown_usd
FROM workspace.candyops.gold_seasonal_exposure
WHERE item_type = 'finished_goods'
ORDER BY scenario_id, factory_id, item_id;


-- ds10_sensitivity : does removing the suspected wrapper constraint change the outcome?
SELECT
  change_tested,
  base_scenario_id,
  test_scenario_id,
  base_bags_ready_on_time,
  test_bags_ready_on_time,
  delta_bags_ready_on_time,
  base_orders_fully_ready,
  test_orders_fully_ready,
  base_incremental_cost_usd,
  test_incremental_cost_usd,
  test_primary_constraint,
  verdict
FROM workspace.candyops.gold_sensitivity;


-- ds11_data_quality : silver + gold check status (counter: failed checks should be 0)
SELECT layer, status, COUNT(*) AS checks
FROM (
  SELECT layer, status FROM workspace.candyops.silver_quality_checks
  UNION ALL
  SELECT layer, status FROM workspace.candyops.gold_validation_results
)
GROUP BY layer, status
ORDER BY layer, status;


-- ds12_sweeps : film delivery date and overtime cap sweeps (line chart: x = param_value, y = bags, color = option)
SELECT
  sweep_name,
  option,
  param_value,
  days_or_hours,
  bags_ready_on_time,
  ROUND(on_time_ready_rate_bags * 100, 1) AS on_time_ready_pct,
  incremental_cost_usd,
  cost_per_incremental_ready_bag_usd,
  primary_constraint
FROM workspace.candyops.gold_sweep
ORDER BY sweep_name, option, days_or_hours;
