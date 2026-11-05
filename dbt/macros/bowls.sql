{% macro eligible_candies(allowed_statuses) %}
with restriction_names as (
    select distinct restriction from {{ ref('restrictions') }}
),

blocked as (
    select distinct r.restriction, a.candy
    from {{ ref('restrictions') }} as r
    inner join {{ ref('gold_candy_allergens') }} as a on a.allergen = r.allergen and a.vintage = 'snapshot_2017'
    where a.status not in ('{{ allowed_statuses | join("', '") }}') or a.n_evidence < {{ var('min_evidence') }}
    union
    -- second source: FiveThirtyEight tags peanut/almond candies; labels can miss them (Butterfinger's only
    -- matches with ingredients were a caramel apple and marshmallow squares "made with" it)
    select distinct r.restriction, p.candy
    from {{ ref('restrictions') }} as r
    inner join {{ ref('gold_candy_profile') }} as p on p.peanut_or_almond
    where r.allergen in ('peanut', 'tree_nut')
)

select n.restriction, p.candy, p.win_percent, p.sugars_100g
from restriction_names as n
cross join {{ ref('gold_candy_profile') }} as p
left anti join blocked as b on b.restriction = n.restriction and b.candy = p.candy
{% endmacro %}
