-- One row per candy and allergen. Evidence = matched products that have an ingredient list; US products only
-- when the candy has at least min_evidence of them (US and EU recipes of the same bar differ).
with scope as (
    select
        candy,
        count_if(is_us and has_ingredients) >= {{ var('min_evidence') }} as us_only
    from {{ ref('silver_candy_matches') }}
    group by candy
),

evidence as (
    select m.candy, a.allergen, a.contains, a.may_contain
    from {{ ref('silver_candy_matches') }} as m
    inner join scope as s on s.candy = m.candy
    inner join {{ ref('silver_product_allergens') }} as a on a.code = m.code
    where m.has_ingredients and (m.is_us or not s.us_only)
),

summary as (
    select
        r.candy,
        t.allergen,
        case when s.us_only then 'us' when s.candy is not null then 'all_countries' else 'no_match' end
            as evidence_scope,
        count(e.candy) as n_evidence,
        avg(cast(e.contains as int)) as contains_share,
        avg(cast(e.contains or e.may_contain as int)) as contains_or_may_share
    from {{ ref('silver_candy_ranking') }} as r
    cross join {{ ref('allergen_terms') }} as t
    left join scope as s on s.candy = r.candy
    left join evidence as e on e.candy = r.candy and e.allergen = t.allergen
    where r.is_candy
    group by r.candy, t.allergen, s.us_only, s.candy
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
