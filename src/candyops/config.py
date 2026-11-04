"""Project constants. CandyOps analyses two public Kaggle datasets; it generates no data of its own."""

DEFAULT_CATALOG = "workspace"
DEFAULT_SCHEMA = "candyops"
DEFAULT_VOLUME = "raw"

# Pinned Kaggle versions, so every run reads the same bytes
OFF_DATASET = "openfoodfacts/world-food-facts/versions/5"
OFF_FILE = "en.openfoodfacts.org.products.tsv"
OFF_ROWS = 356_001  # data rows when split on "\n" only; 26 rows hold a stray "\r" that other readers split on
RANKING_DATASET = "fivethirtyeight/the-ultimate-halloween-candy-power-ranking/versions/1"
RANKING_FILE = "candy-data.csv"
RANKING_ROWS = 85

DATA_NOTICE = (
    "Data: Open Food Facts (ODbL, openfoodfacts.org) and FiveThirtyEight's Ultimate Halloween Candy Power "
    "Ranking (MIT), 2017 snapshots from Kaggle. Allergen flags are parsed from crowdsourced ingredient "
    "lists, are not medical advice, and can be out of date: always read the package label."
)

# Open Food Facts daily change feed: one file per day of changed products, kept upstream for about two weeks
FEED_BASE_URL = "https://static.openfoodfacts.org/data/delta/"
FEED_SCHEMA = ("code STRING, product_name STRING, brands STRING, countries_tags ARRAY<STRING>, "
               "ingredients_text STRING, allergens_tags ARRAY<STRING>, traces_tags ARRAY<STRING>, "
               "serving_size STRING, last_modified_t STRING, nutriments STRUCT<sugars_100g: STRING>")
