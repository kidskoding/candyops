-- Current version of every product edited since the change feed started, upserted on barcode.
-- Incremental: each run reads only bronze rows newer than the last run and MERGEs them in.
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='code') }}

with typed as (
    select
        {{ clean('code') }} as code,
        try_cast({{ clean('last_modified_t') }} as bigint) as last_modified_t,
        {{ clean('product_name') }} as product_name,
        {{ clean('brands') }} as brands,
        coalesce(array_contains(countries_tags, 'en:united-states'), false) as is_us,
        {{ clean('ingredients_text') }} as ingredients_text,
        nullif(array_join(allergens_tags, ', '), '') as allergens,
        nullif(array_join(traces_tags, ', '), '') as traces,
        {{ clean('serving_size') }} as serving_size,
        try_cast({{ clean('nutriments.sugars_100g') }} as double) as sugars_100g_raw,
        _source_file,
        _ingested_at
    from {{ source('bronze', 'bronze_off_changes') }}
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

standardized as (
    {{ standard_products('typed', ['_source_file', '_ingested_at']) | indent(4) }}
)

select * from standardized
where code is not null
qualify row_number() over (
    partition by code
    order by last_modified_t desc nulls last, _ingested_at desc
) = 1
