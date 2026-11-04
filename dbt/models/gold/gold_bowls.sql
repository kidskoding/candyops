-- The 10 most popular candies a host can hand out under each restriction. A candy is allowed only when every
-- restricted allergen is 'not_listed' on enough evidence; 'unknown', 'varies' and 'may_contain' all exclude it,
-- and nut-free bowls also drop every candy the ranking itself tags as peanut/almond.
with restriction_names as (
    select distinct restriction from {{ ref('restrictions') }}
),

blocked as (
    select distinct r.restriction, a.candy
    from {{ ref('restrictions') }} as r
    inner join {{ ref('gold_candy_allergens') }} as a on a.allergen = r.allergen and a.vintage = 'snapshot_2017'
    where a.status <> 'not_listed' or a.n_evidence < {{ var('min_evidence') }}
    union
    -- second source: FiveThirtyEight tags peanut/almond candies; labels can miss them (Butterfinger's only
    -- matches with ingredients were a caramel apple and marshmallow squares "made with" it)
    select distinct r.restriction, p.candy
    from {{ ref('restrictions') }} as r
    inner join {{ ref('gold_candy_profile') }} as p on p.peanut_or_almond
    where r.allergen in ('peanut', 'tree_nut')
),

eligible as (
    select n.restriction, p.candy, p.win_percent, p.sugars_100g
    from restriction_names as n
    cross join {{ ref('gold_candy_profile') }} as p
    left anti join blocked as b on b.restriction = n.restriction and b.candy = p.candy
),

ranked as (
    select
        *,
        row_number() over (partition by restriction order by win_percent desc, candy) as bowl_rank,
        count(*) over (partition by restriction) as n_eligible
    from eligible
)

select restriction, bowl_rank, candy, win_percent, sugars_100g, n_eligible
from ranked
where bowl_rank <= {{ var('bowl_size') }}
