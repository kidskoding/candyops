-- Every candy in a restricted bowl must be not_listed for each restricted allergen.
select b.restriction, b.candy, a.allergen, a.status
from {{ ref('gold_bowls') }} as b
inner join {{ ref('restrictions') }} as r on r.restriction = b.restriction
inner join {{ ref('gold_candy_allergens') }} as a
    on a.candy = b.candy and a.allergen = r.allergen and a.vintage = 'snapshot_2017'
where a.status <> 'not_listed' or a.n_evidence < {{ var('min_evidence') }}
