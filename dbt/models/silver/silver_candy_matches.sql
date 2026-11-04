-- Each ranked candy -> its Open Food Facts products, by the hand-written rules in seeds/candy_aliases.csv.
select
    r.candy,
    p.code,
    p.product_name,
    p.brands,
    p.is_us,
    p.ingredients_text is not null as has_ingredients,
    p.sugars_100g,
    p.serving_g
from {{ ref('silver_products') }} as p
inner join {{ ref('candy_aliases') }} as a
    on p.search_text rlike a.include
   and (a.exclude is null or not p.search_text rlike a.exclude)
inner join {{ ref('silver_candy_ranking') }} as r
    on r.candy = a.competitorname
where not p.search_text rlike {{ rule('not_candy') }}
