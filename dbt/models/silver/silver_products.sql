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

standardized as (
    {{ standard_products('typed') | indent(4) }}
)

select * from standardized
where code is not null
qualify row_number() over (
    partition by code
    order by last_modified_t desc nulls last, ingredients_text is null, product_name
) = 1
