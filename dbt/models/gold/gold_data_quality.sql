-- What the raw data looked like and what cleaning did to it.
{% set metrics = [
    ('bronze_rows', "(select count(*) from " ~ source('bronze', 'bronze_off_products') ~ ")"),
    ('silver_rows', "(select count(*) from " ~ ref('silver_products') ~ ")"),
    ('rows_without_barcode', "(select count(*) from " ~ source('bronze', 'bronze_off_products') ~ " where nullif(trim(code), '') is null)"),
    ('duplicate_barcode_rows_dropped', "(select count(*) - count(distinct code) from " ~ source('bronze', 'bronze_off_products') ~ " where nullif(trim(code), '') is not null)"),
    ('products_with_ingredients', "(select count_if(ingredients_text is not null) from " ~ ref('silver_products') ~ ")"),
    ('products_with_allergen_field', "(select count_if(allergens is not null) from " ~ ref('silver_products') ~ ")"),
    ('sugar_values_out_of_range', "(select count_if(sugars_out_of_range) from " ~ ref('silver_products') ~ ")"),
    ('us_products', "(select count_if(is_us) from " ~ ref('silver_products') ~ ")"),
    ('ranked_candies', "(select count_if(is_candy) from " ~ ref('silver_candy_ranking') ~ ")"),
    ('candies_matched', "(select count(distinct candy) from " ~ ref('silver_candy_matches') ~ ")"),
    ('candies_with_enough_evidence', "(select count(*) from " ~ ref('gold_candy_profile') ~ " where n_evidence >= " ~ var('min_evidence') ~ ")"),
    ('matched_products', "(select count(distinct code) from " ~ ref('silver_candy_matches') ~ ")"),
] %}
{% for name, expr in metrics %}
select {{ loop.index }} as sort_order, '{{ name }}' as metric, cast({{ expr }} as bigint) as value
{{ 'union all' if not loop.last }}
{% endfor %}
