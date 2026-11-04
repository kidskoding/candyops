{# Shared by both product sources. `typed` must provide code, last_modified_t, product_name, brands, is_us,
   ingredients_text, allergens, traces, serving_size, sugars_100g_raw. #}
{% macro standard_products(typed, extra_columns=[]) -%}
with parsed as (
    select
        *,
        try_cast(replace(regexp_extract(lower(serving_size), r'([0-9]+(?:[.,][0-9]+)?) ?g\b', 1), ',', '.') as double)
            as serving_grams_label,
        try_cast(replace(regexp_extract(lower(serving_size), r'([0-9]+(?:[.,][0-9]+)?) ?oz\b', 1), ',', '.') as double)
            * 28.3495 as serving_grams_from_oz
    from {{ typed }}
)

select
    code,
    last_modified_t,
    product_name,
    brands,
    is_us,
    ingredients_text,
    allergens,
    traces,
    serving_size,
    case when coalesce(serving_grams_label, serving_grams_from_oz) > 0
          and coalesce(serving_grams_label, serving_grams_from_oz) <= 500
         then round(coalesce(serving_grams_label, serving_grams_from_oz), 1) end as serving_g,
    case when sugars_100g_raw between 0 and 100 then sugars_100g_raw end as sugars_100g,
    coalesce(not sugars_100g_raw between 0 and 100, false) as sugars_out_of_range,
    {{ normalize_text("concat_ws(' || ', coalesce(product_name, ''), coalesce(brands, ''))") }} as search_text
    {%- for c in extra_columns %},
    {{ c }}
    {%- endfor %}
from parsed
{%- endmacro %}
