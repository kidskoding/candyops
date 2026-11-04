-- One typed row per barcode. Parsed on "\n" only, the pinned file has no duplicate barcodes (a reader that also
-- splits on "\r" invents 25); the dedupe keeps the latest edit if a later version adds some.
with typed as (
    select
        {{ clean('code') }} as code,
        try_cast({{ clean('last_modified_t') }} as bigint) as last_modified_t,
        {{ clean('product_name') }} as product_name,
        {{ clean('brands') }} as brands,
        coalesce(countries_tags, '') like '%en:united-states%' as is_us,
        {{ clean('ingredients_text') }} as ingredients_text,
        {{ clean('allergens') }} as allergens,
        {{ clean('traces') }} as traces,
        {{ clean('serving_size') }} as serving_size,
        try_cast({{ clean('sugars_100g') }} as double) as sugars_100g_raw
    from {{ source('bronze', 'bronze_off_products') }}
),

parsed as (
    select
        *,
        try_cast(replace(regexp_extract(lower(serving_size), r'([0-9]+(?:[.,][0-9]+)?) ?g\b', 1), ',', '.') as double)
            as serving_grams_label,
        try_cast(replace(regexp_extract(lower(serving_size), r'([0-9]+(?:[.,][0-9]+)?) ?oz\b', 1), ',', '.') as double)
            * 28.3495 as serving_grams_from_oz
    from typed
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
from parsed
where code is not null
qualify row_number() over (
    partition by code
    order by last_modified_t desc nulls last, ingredients_text is null, product_name
) = 1
