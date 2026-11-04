-- Why the hand-written rules: matching on the candy's name alone misses spelling variants and pulls in
-- non-candy products (coffee creamer, ice cream, cereal).
with candies as (
    select candy, {{ normalize_text('candy') }} as name_norm
    from {{ ref('silver_candy_ranking') }}
    where is_candy
),

naive as (
    select c.candy, p.code, p.is_us, p.search_text rlike {{ rule('not_candy') }} as not_candy
    from {{ ref('silver_products') }} as p
    inner join candies as c on p.search_text rlike concat(r'\b\Q', c.name_norm, r'\E\b')
),

curated as (
    select candy, code, is_us, false as not_candy
    from {{ ref('silver_candy_matches') }}
    where vintage = 'snapshot_2017'
)

{% for method in ['naive', 'curated'] %}
select
    '{{ method }}' as method,
    count(distinct candy) as candies_matched,
    (select count(*) from candies) as candies_total,
    count(distinct code) as products_matched,
    count(distinct case when is_us then code end) as us_products_matched,
    count(distinct case when not_candy then code end) as non_candy_products
from {{ method }}
{{ 'union all' if not loop.last }}
{% endfor %}
