-- One row per vintage, candy and allergen. Evidence = matched products that have an ingredient list; US products only
-- when the candy has at least min_us_evidence of them (US and EU recipes of the same bar differ).
with scope as (
    select
        vintage,
        candy,
        count_if(is_us and has_ingredients) >= {{ var('min_us_evidence') }} as us_only
    from {{ ref('silver_candy_matches') }}
    group by vintage, candy
),

evidence as (
    select m.vintage, m.candy, a.allergen, a.contains, a.may_contain
    from {{ ref('silver_candy_matches') }} as m
    inner join scope as s on s.vintage = m.vintage and s.candy = m.candy
    inner join {{ ref('silver_product_allergens') }} as a on a.vintage = m.vintage and a.code = m.code
    where m.has_ingredients and (m.is_us or not s.us_only)
),

summary as (
    select
        v.vintage,
        r.candy,
        t.allergen,
        case when s.us_only then 'us' when s.candy is not null then 'all_countries' else 'no_match' end
            as evidence_scope,
        count(e.candy) as n_evidence,
        avg(cast(e.contains as int)) as contains_share,
        avg(cast(e.contains or e.may_contain as int)) as contains_or_may_share
    from {{ ref('silver_candy_ranking') }} as r
    cross join {{ ref('allergen_terms') }} as t
    cross join (select explode(array('snapshot_2017', 'change_feed')) as vintage) as v
    left join scope as s on s.vintage = v.vintage and s.candy = r.candy
    left join evidence as e on e.vintage = v.vintage and e.candy = r.candy and e.allergen = t.allergen
    where r.is_candy
    group by v.vintage, r.candy, t.allergen, s.us_only, s.candy
)

select
    *,
    case
        when n_evidence = 0 then 'unknown'
        when contains_share >= 0.5 then 'contains'
        when contains_share > 0 then 'varies'
        when contains_or_may_share > 0 then 'may_contain'
        else 'not_listed'
    end as status
from summary
