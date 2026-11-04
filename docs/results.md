# candyops results

**Executed** 2026-11-04 16:33 UTC against `workspace.candyops_dev` on Databricks (regenerate: `scripts/write_results.py`).

Data: Open Food Facts (ODbL) and FiveThirtyEight's Candy Power Ranking (MIT), 2017 snapshots from Kaggle, plus the
Open Food Facts daily change feed (products edited since the feed archive started).
Allergen statuses are parsed from crowdsourced ingredient lists, are not medical advice, and can be out of date.

## 1. Cleaning

| Metric | Value |
|---|---|
| bronze_rows | 356001 |
| silver_rows | 356001 |
| rows_without_barcode | 0 |
| duplicate_barcode_rows_dropped | 0 |
| products_with_ingredients | 283859 |
| products_with_allergen_field | 37177 |
| sugar_values_out_of_range | 20 |
| us_products | 173709 |
| ranked_candies | 83 |
| candies_matched | 68 |
| candies_with_enough_evidence | 59 |
| matched_products | 1217 |
| feed_files_archived | 13 |
| feed_rows_loaded | 98694 |
| feed_products_current | 84556 |
| feed_candy_products | 348 |
| feed_candies_with_enough_evidence | 21 |

## 2. Bowls

Each bowl holds the 10 most popular candies whose matched labels list none of the
restricted allergens (on at least 2 products with an ingredient list). `popularity_kept_pct` compares the bowl's average
win rate with the unrestricted bowl's.

| Restriction | Candies allowed | Avg win % | Popularity kept % | Median sugar g/100g | Bowl, most popular first |
|---|---|---|---|---|---|
| no_restriction | 83 | 76.28 | 100.0 | 51.7 | Reese's Peanut Butter cup, Reese's Miniatures, Twix, Kit Kat, Snickers, Reese's pieces, Milky Way, Reese's stuffed with pieces, Peanut butter M&M's, Nestle Butterfinger |
| gluten_free | 37 | 67.31 | 88.2 | 52.9 | Reese's Peanut Butter cup, Reese's Miniatures, Reese's pieces, Peanut butter M&M's, Peanut M&Ms, Skittles original, Sour Patch Kids, Junior Mints, Haribo Gold Bears, Nerds |
| peanut_free | 43 | 59.46 | 78.0 | 69.1 | Starburst, Rolo, Skittles original, Sour Patch Kids, Hershey's Special Dark, Junior Mints, Haribo Gold Bears, Nerds, Skittles wildberry, Swedish Fish |
| nut_free | 41 | 58.83 | 77.1 | 69.4 | Starburst, Rolo, Skittles original, Sour Patch Kids, Junior Mints, Haribo Gold Bears, Nerds, Skittles wildberry, Swedish Fish, Lifesavers big ring gummies |
| milk_free | 30 | 56.91 | 74.6 | 64.7 | Starburst, Skittles original, Sour Patch Kids, Haribo Gold Bears, Nerds, Skittles wildberry, Swedish Fish, Lifesavers big ring gummies, Air Heads, Haribo Sour Bears |
| free_of_all_six | 18 | 52.39 | 68.7 | 64.7 | Skittles original, Sour Patch Kids, Haribo Gold Bears, Skittles wildberry, Swedish Fish, Lifesavers big ring gummies, Haribo Sour Bears, Welch's Fruit Snacks, Runts, Dots |

## 3. Matching: name only vs curated rules

| Method | Candies matched | Of | Products | US products | Not candy |
|---|---|---|---|---|---|
| naive | 53 | 83 | 921 | 590 | 80 |
| curated | 68 | 83 | 1217 | 746 | 0 |

## 4. Is the 2017 answer still true?

Allergen status per candy in the 2017 snapshot next to the products edited since the change feed started. A candy is
compared only when it has at least 2 current products with an ingredient list; the bowls above still use 2017.

| Each candy, 2017 vs now | Candies |
|---|---|
| not enough current data | 62 |
| at least one allergen changed | 12 |
| all compared allergens unchanged | 7 |
| newly covered | 2 |

| Candy | Allergen | 2017 | 2017 products | Now | Current products | Comparison |
|---|---|---|---|---|---|---|
| Hershey's Milk Chocolate | peanut | varies | 3 | not_listed | 3 | changed |
| Hershey's Milk Chocolate | tree_nut | not_listed | 3 | may_contain | 3 | changed |
| Kit Kat | peanut | may_contain | 28 | varies | 41 | changed |
| M&M's | egg | varies | 19 | not_listed | 27 | changed |
| M&M's | peanut | may_contain | 19 | varies | 27 | changed |
| M&M's | tree_nut | not_listed | 19 | varies | 27 | changed |
| Milky Way | egg | varies | 4 | contains | 4 | changed |
| Nestle Crunch | soy | varies | 19 | may_contain | 7 | changed |
| Nestle Smarties | egg | varies | 33 | not_listed | 8 | changed |
| Nestle Smarties | peanut | varies | 33 | may_contain | 8 | changed |
| Peanut M&Ms | tree_nut | varies | 26 | may_contain | 4 | changed |
| Peanut butter M&M's | tree_nut | may_contain | 4 | varies | 3 | changed |
| Rolo | soy | contains | 4 | varies | 5 | changed |
| Snickers | egg | varies | 27 | contains | 25 | changed |
| Twix | peanut | varies | 36 | may_contain | 20 | changed |
| Werther's Original Caramel | gluten | contains | 17 | varies | 9 | changed |
| 3 Musketeers | egg | contains | 1 | contains | 3 | newly_covered |
| 3 Musketeers | gluten | not_listed | 1 | not_listed | 3 | newly_covered |
| 3 Musketeers | milk | contains | 1 | contains | 3 | newly_covered |
| 3 Musketeers | peanut | not_listed | 1 | may_contain | 3 | newly_covered |
| 3 Musketeers | soy | contains | 1 | contains | 3 | newly_covered |
| 3 Musketeers | tree_nut | not_listed | 1 | not_listed | 3 | newly_covered |
| Nestle Butterfinger | egg | unknown | 0 | not_listed | 2 | newly_covered |
| Nestle Butterfinger | gluten | unknown | 0 | not_listed | 2 | newly_covered |
| Nestle Butterfinger | milk | unknown | 0 | contains | 2 | newly_covered |
| Nestle Butterfinger | peanut | unknown | 0 | contains | 2 | newly_covered |
| Nestle Butterfinger | soy | unknown | 0 | contains | 2 | newly_covered |
| Nestle Butterfinger | tree_nut | unknown | 0 | not_listed | 2 | newly_covered |

## 5. Every candy

Statuses: `contains` (most evidence lists it), `varies` (some products do), `may_contain` (warning only),
`not_listed`, `unknown` (no matched product with an ingredient list).

| Rank | Candy | Win % | Products | With ingredients | Scope | Peanut | Tree nut | Milk | Gluten | Soy | Egg | Sugar g/100g |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Reese's Peanut Butter cup | 84.18029 | 26 | 18 | us | contains | not_listed | contains | not_listed | contains | not_listed | 52.3 |
| 2 | Reese's Miniatures | 81.866257 | 19 | 15 | us | contains | not_listed | contains | not_listed | contains | not_listed | 52.3 |
| 3 | Twix | 81.642914 | 50 | 36 | all_countries | varies | varies | contains | contains | contains | not_listed | 48.8 |
| 4 | Kit Kat | 76.7686 | 62 | 28 | all_countries | may_contain | varies | contains | contains | varies | not_listed | 49.3 |
| 5 | Snickers | 76.673782 | 50 | 27 | all_countries | contains | varies | contains | varies | contains | varies | 51.5 |
| 6 | Reese's pieces | 73.43499 | 7 | 5 | all_countries | contains | not_listed | varies | not_listed | contains | not_listed | 51.8 |
| 7 | Milky Way | 73.099556 | 5 | 4 | all_countries | may_contain | may_contain | contains | contains | contains | varies | 54.4 |
| 8 | Reese's stuffed with pieces | 72.887901 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 9 | Peanut butter M&M's | 71.46505 | 10 | 4 | all_countries | contains | may_contain | contains | not_listed | contains | not_listed | 42.0 |
| 10 | Nestle Butterfinger | 70.735641 | 1 | 0 | all_countries | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 11 | Peanut M&Ms | 69.483788 | 33 | 26 | all_countries | contains | varies | contains | not_listed | contains | not_listed | 53.5 |
| 12 | 3 Musketeers | 67.602936 | 1 | 1 | all_countries | not_listed | not_listed | contains | not_listed | contains | contains | 66.2 |
| 13 | Starburst | 67.037628 | 8 | 3 | all_countries | not_listed | not_listed | not_listed | varies | not_listed | not_listed | 50.0 |
| 14 | 100 Grand | 66.971725 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 15 | M&M's | 66.574585 | 100 | 19 | us | may_contain | not_listed | contains | varies | contains | varies | 53.8 |
| 16 | Nestle Crunch | 66.47068 | 29 | 19 | all_countries | may_contain | varies | contains | contains | varies | not_listed | 42.7 |
| 17 | Rolo | 65.716286 | 8 | 4 | all_countries | not_listed | not_listed | contains | may_contain | contains | not_listed | 43.1 |
| 18 | Milky Way Simply Caramel | 64.35334 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 19 | Skittles original | 63.08514 | 26 | 13 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 89.8 |
| 20 | Hershey's Krackel | 62.284481 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 21 | Milky Way Midnight | 60.800701 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 22 | Sour Patch Kids | 59.863998 | 5 | 4 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 64.3 |
| 23 | Snickers Crisper | 59.529251 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 24 | Hershey's Special Dark | 59.236122 | 3 | 2 | all_countries | not_listed | contains | contains | contains | contains | not_listed | 27.4 |
| 25 | Junior Mints | 57.21925 | 17 | 17 | us | not_listed | not_listed | varies | not_listed | contains | not_listed | 80.0 |
| 26 | Haribo Gold Bears | 57.11974 | 18 | 3 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 46.0 |
| 27 | Baby Ruth | 56.914547 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 28 | Hershey's Milk Chocolate | 56.490501 | 3 | 3 | us | varies | not_listed | contains | varies | contains | not_listed | 55.8 |
| 29 | Hershey's Kisses | 55.375454 | 2 | 0 | all_countries | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 30 | Nerds | 55.354046 | 13 | 3 | us | not_listed | not_listed | not_listed | not_listed | varies | may_contain | 93.3 |
| 31 | Skittles wildberry | 55.103695 | 3 | 2 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 90.2 |
| 32 | Milk Duds | 55.064072 | 2 | 1 | all_countries | not_listed | not_listed | contains | not_listed | not_listed | not_listed | 51.3 |
| 33 | Swedish Fish | 54.861111 | 15 | 15 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 73.8 |
| 34 | Mr Good Bar | 54.526451 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 35 | Lifesavers big ring gummies | 52.911392 | 12 | 12 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 65.0 |
| 36 | Sour Patch Tricksters | 52.825947 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 37 | Air Heads | 52.341465 | 58 | 56 | us | not_listed | not_listed | not_listed | varies | contains | not_listed | 56.3 |
| 38 | Haribo Sour Bears | 51.41243 | 4 | 4 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 53.7 |
| 39 | Almond Joy | 50.347546 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 40 | Tootsie Roll Snack Bars | 49.653503 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 41 | Whoppers | 49.524113 | 5 | 5 | us | not_listed | not_listed | contains | contains | contains | not_listed | 58.5 |
| 42 | Tootsie Pop | 48.982651 | 4 | 4 | us | not_listed | not_listed | contains | not_listed | contains | not_listed | 59.4 |
| 43 | Mounds | 47.829754 | 3 | 2 | all_countries | not_listed | not_listed | contains | not_listed | contains | not_listed | 41.2 |
| 44 | Trolli Sour Bites | 47.173229 | 10 | 10 | us | not_listed | not_listed | not_listed | varies | not_listed | not_listed | 67.5 |
| 45 | Gobstopper | 46.783348 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 46 | Mike & Ike | 46.411716 | 38 | 38 | us | not_listed | not_listed | not_listed | varies | varies | not_listed | 62.5 |
| 47 | Payday | 46.296597 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 48 | Smarties candy | 45.995827 | 27 | 27 | us | varies | varies | varies | varies | varies | varies | 85.7 |
| 49 | Tootsie Roll Midgies | 45.736748 | 15 | 15 | us | not_listed | not_listed | contains | not_listed | contains | not_listed | 50.0 |
| 50 | Twizzlers | 45.466282 | 1 | 0 | all_countries | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 51 | Welch's Fruit Snacks | 44.375519 | 21 | 20 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 43.1 |
| 52 | Fruit Chews | 43.088924 | 11 | 11 | us | not_listed | not_listed | contains | not_listed | contains | not_listed | 50.0 |
| 53 | Tootsie Roll Juniors | 43.068897 | 5 | 5 | us | not_listed | not_listed | not_listed | not_listed | contains | not_listed | 79.7 |
| 54 | Runts | 42.849144 | 7 | 7 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 86.7 |
| 55 | Dots | 42.272076 | 12 | 12 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 52.5 |
| 56 | Haribo Twin Snakes | 42.178772 | 2 | 2 | all_countries | not_listed | not_listed | not_listed | contains | not_listed | not_listed | 44.2 |
| 57 | Werther's Original Caramel | 41.904308 | 36 | 17 | us | not_listed | varies | contains | contains | contains | not_listed | 46.3 |
| 58 | Laffy Taffy | 41.389557 | 14 | 14 | us | not_listed | not_listed | not_listed | not_listed | varies | contains | 53.5 |
| 59 | Pop Rocks | 41.265511 | 6 | 5 | us | not_listed | not_listed | contains | varies | varies | not_listed | 84.2 |
| 60 | Dum Dums | 39.460556 | 5 | 5 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 76.9 |
| 61 | Now & Later | 39.4468 | 17 | 17 | us | not_listed | not_listed | not_listed | not_listed | contains | contains | 59.0 |
| 62 | Fun Dip | 39.185505 | 14 | 14 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 91.7 |
| 63 | Lemonhead | 39.141056 | 15 | 15 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 75.8 |
| 64 | Warheads | 39.011898 | 27 | 27 | us | may_contain | not_listed | varies | varies | varies | not_listed | 62.5 |
| 65 | Charleston Chew | 38.975037 | 3 | 3 | us | not_listed | not_listed | contains | not_listed | contains | contains | 57.9 |
| 66 | Candy Corn | 38.010963 | 121 | 121 | us | not_listed | not_listed | varies | varies | varies | contains | 71.8 |
| 67 | Nestle Smarties | 37.887188 | 43 | 33 | all_countries | varies | varies | contains | contains | varies | varies | 58.7 |
| 68 | Pixie Sticks | 37.722336 | 1 | 1 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 95.0 |
| 69 | Red vines | 37.348522 | 13 | 13 | us | not_listed | not_listed | not_listed | contains | not_listed | not_listed | 40.0 |
| 70 | Chewey Lemonhead Fruit Mix | 36.017628 | 19 | 19 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 71.8 |
| 71 | Ring pop | 35.290756 | 19 | 19 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 80.0 |
| 72 | Sixlets | 34.722 | 52 | 52 | us | not_listed | not_listed | contains | not_listed | contains | not_listed | 71.4 |
| 73 | Strawberry bon bons | 34.578991 | 7 | 7 | us | not_listed | not_listed | varies | not_listed | varies | varies | 71.4 |
| 74 | Caramel Apple Pops | 34.517681 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
| 75 | Haribo Happy Cola | 34.158958 | 15 | 8 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 45.0 |
| 76 | Sugar Babies | 33.43755 | 1 | 1 | all_countries | not_listed | not_listed | contains | not_listed | contains | not_listed | 73.2 |
| 77 | Sugar Daddy | 32.230995 | 1 | 1 | all_countries | not_listed | not_listed | contains | not_listed | contains | not_listed | 60.5 |
| 78 | Root Beer Barrels | 29.703691 | 17 | 17 | us | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 71.4 |
| 79 | Jawbusters | 28.127439 | 1 | 1 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 94.1 |
| 80 | Super Bubble | 27.303865 | 2 | 2 | all_countries | not_listed | not_listed | not_listed | not_listed | not_listed | not_listed | 74.4 |
| 81 | Chiclets | 24.524988 | 7 | 6 | us | not_listed | not_listed | not_listed | not_listed | contains | not_listed | 66.7 |
| 82 | Boston Baked Beans | 23.417824 | 16 | 16 | us | contains | not_listed | not_listed | not_listed | not_listed | not_listed | 66.7 |
| 83 | Nik L Nip | 22.445341 | 0 | 0 | no_match | unknown | unknown | unknown | unknown | unknown | unknown |  |
