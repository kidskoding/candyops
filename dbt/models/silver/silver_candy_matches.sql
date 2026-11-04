-- Each ranked candy -> its Open Food Facts products, by the hand-written rules in seeds/candy_aliases.csv.
-- vintage: snapshot_2017 (the pinned Kaggle file) or change_feed (products edited since the feed started).
with products as (
    {% for vintage, model in [('snapshot_2017', 'silver_products'), ('change_feed', 'silver_product_changes')] -%}
    select '{{ vintage }}' as vintage, code, product_name, brands, is_us, ingredients_text, sugars_100g, serving_g,
           search_text
    from {{ ref(model) }}
    {{ 'union all' if not loop.last }}
    {% endfor %}
)

select
    p.vintage,
    r.candy,
    p.code,
    p.product_name,
    p.brands,
    p.is_us,
    p.ingredients_text is not null as has_ingredients,
    p.sugars_100g,
    p.serving_g
from products as p
inner join {{ ref('candy_aliases') }} as a
    on p.search_text rlike a.include
   and (a.exclude is null or not p.search_text rlike a.exclude)
inner join {{ ref('silver_candy_ranking') }} as r
    on r.candy = a.competitorname
where not p.search_text rlike {{ rule('not_candy') }}
