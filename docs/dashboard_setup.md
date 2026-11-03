# CandyOps dashboard — manual assembly (Databricks AI/BI dashboard)

Prerequisite: notebooks 01 → 02 → 03 finished without errors. All data is synthetic.

## 1. Create the dashboard and datasets

1. Left sidebar → **Dashboards** → **Create dashboard**. Rename it **CandyOps — Halloween Recovery (synthetic data)**.
2. Open the **Data** tab → **Create from SQL**. Create one dataset per query in `sql/dashboard_queries.sql`.
   Paste the query **without** its comment header and name the dataset after the comment tag
   (`ds01_scenario_kpis`, `ds01b_kpi_tiles`, `ds02_orders_at_risk`, … `ds11_data_quality`). Click **Run** on each one to confirm it returns rows.
3. If you used a catalog or schema other than `workspace.candyops`, find-and-replace that prefix first.

## 2. Global filter

Add a **Filter → Single value** widget at the top, titled **Scenario**, on field `scenario_id`. Connect it to
`ds03`, `ds04`, `ds05`, `ds07` and `ds08` (and `ds09` if you want). Default value: `S1_NO_RECOVERY`.
Leave `ds01`, `ds01b`, `ds02`, `ds06`, `ds10` and `ds11` unfiltered, because they compare scenarios.

## 3. Layout (top to bottom)

Colors: use **orange `#F97316`** for the main or recovery measure and **purple `#7C3AED`** for the
comparison or loss measure. Set them in each widget under **Color → series colors**. Keep the background default for
readability.

| # | Title | Dataset | Visualization | Fields |
|---|---|---|---|---|
| 0 | *Text box*: "CandyOps — synthetic demo. Ready-to-ship = bags allocated at the dispatch factory by the deadline day. Modeled outcomes, not real results." | — | Text | — |
| 1 | On-time ready-to-ship rate: no recovery vs overtime vs transfer | ds01b | **Counter** ×3 | Values `no_recovery_ready_pct`, `overtime_ready_pct`, `transfer_ready_pct` (one counter each, suffix %) |
| 2 | Bags at risk after breakdown | ds02 | **Counter** | Value `SUM(short_bags_no_recovery)` |
| 3 | Orders at risk | ds02 | **Counter** | Value `COUNT(order_id)` |
| 4 | Bags ready on time by scenario | ds01 | **Bar** | X `scenario_id`; Y `bags_ready_on_time` (orange); sort by X |
| 5 | Incremental cost by scenario (USD, modeled) | ds01 | **Bar** | X `scenario_id`; Y `overtime_cost_usd`, `alternate_run_cost_usd`, `transfer_freight_usd` (stacked; orange, purple, grey) |
| 6 | Scenario scorecard | ds01 | **Table** | `scenario_id`, `orders_fully_ready`, `on_time_ready_pct`, `incremental_ready_bags_vs_s1`, `incremental_cost_usd`, `cost_per_incremental_ready_bag_usd`, `primary_constraint` |
| 7 | Orders at risk after the breakdown | ds02 | **Table** | all columns |
| 8 | Order readiness (selected scenario) | ds03 | **Table** | `order_id`, `customer_name`, `sku_id`, `ready_to_ship_deadline`, `order_qty_bags`, `ready_on_time_bags`, `status`; conditional format `status` = PARTIAL/NOT READY → purple |
| 9 | Production vs plan | ds04 | **Bar** (grouped) | X `date`; Y `SUM(planned_bags)` (purple), `SUM(good_bags)` (orange) |
| 10 | Runtime and downtime by line | ds05 | **Bar** (stacked) | X `date`; Y `runtime_standard_hours` (orange), `runtime_overtime_hours` (light orange), `downtime_hours` (purple), `idle_standard_hours` (grey); Group/facet by `line_id` |
| 11 | Quality yield and scrap | ds06 | **Table** | `scenario_id`, `line_id`, `quality_yield_pct`, `reject_bags`, `scrap_kg` |
| 12 | Halloween film on hand | ds07 | **Line** | X `date`; Y `closing_qty`; Color `material_id`; filter `factory_id` = `SGT` to show the Southgate bottleneck |
| 13 | Where spare capacity went | ds08 | **Table** | `date`, `line_id`, `spare_hours`, `recovery_runtime_hours`, `material_blocked_hours`, `unused_hours`, `status` |
| 14 | Sensitivity: Southgate film delivered Oct 27 | ds10 | **Table** (or two Counters: `base_bags_ready_on_time`, `test_bags_ready_on_time`) | include `verdict` |
| 15 | Halloween bags left after Oct 31 | ds09 | **Bar** | X `scenario_id`; Y `SUM(bags_remaining)` (purple); tooltip `SUM(assumed_markdown_usd)`, title suffix "(markdown = assumption)" |
| 16 | Data-quality checks | ds11 | **Table** | `layer`, `status`, `checks` |

## 4. Finish

* Widget titles: turn **Show title** on and use the titles above.
* **Publish** the dashboard (embed credentials off/on as you prefer). The dashboard reads only from the project schema.
* For screenshots, select `S3_TRANSFER` in the Scenario filter so widgets 12 and 13 show the wrapper bottleneck.

## Why there is no OEE tile

The simulation runs lines at their ideal rate by construction, so OEE's performance component would be 100%
by assumption. The dashboard shows the supported components instead: availability (runtime / scheduled hours),
downtime hours, and quality yield.
