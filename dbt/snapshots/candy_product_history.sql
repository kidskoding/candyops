{% snapshot candy_product_history %}
{# Type 2 history of every candy product in the change feed: a new row each time its label is edited. #}
{{ config(unique_key='code', strategy='timestamp', updated_at='updated_at') }}
select
    p.code,
    p.product_name,
    p.brands,
    p.is_us,
    p.ingredients_text,
    p.allergens,
    p.traces,
    timestamp_seconds(p.last_modified_t) as updated_at
from {{ ref('silver_product_changes') }} as p
where p.last_modified_t is not null
  and p.code in (select code from {{ ref('silver_candy_matches') }} where vintage = 'change_feed')
{% endsnapshot %}
