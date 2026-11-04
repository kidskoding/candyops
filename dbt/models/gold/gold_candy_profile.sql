with matches as (
    select
        candy,
        count(*) as n_products,
        count_if(is_us) as n_us_products,
        count_if(has_ingredients) as n_with_ingredients,
        median(sugars_100g) as sugars_100g,
        median(serving_g) as serving_g
    from {{ ref('silver_candy_matches') }}
    group by candy
),

allergens as (
    select
        candy,
        max(evidence_scope) as evidence_scope,
        max(n_evidence) as n_evidence,
        {% for a in ['peanut', 'tree_nut', 'milk', 'gluten', 'soy', 'egg'] -%}
        max(case when allergen = '{{ a }}' then status end) as {{ a }}{{ ',' if not loop.last }}
        {% endfor %}
    from {{ ref('gold_candy_allergens') }}
    group by candy
)

select
    r.candy,
    r.win_percent,
    rank() over (order by r.win_percent desc) as popularity_rank,
    r.chocolate,
    r.fruity,
    r.peanut_or_almond,
    coalesce(m.n_products, 0) as n_products,
    coalesce(m.n_us_products, 0) as n_us_products,
    coalesce(m.n_with_ingredients, 0) as n_with_ingredients,
    a.evidence_scope,
    a.n_evidence,
    round(m.sugars_100g, 1) as sugars_100g,
    round(m.serving_g, 1) as serving_g,
    round(m.sugars_100g * m.serving_g / 100, 1) as sugars_per_serving_g,
    a.peanut,
    a.tree_nut,
    a.milk,
    a.gluten,
    a.soy,
    a.egg
from {{ ref('silver_candy_ranking') }} as r
left join matches as m on m.candy = r.candy
left join allergens as a on a.candy = r.candy
where r.is_candy
