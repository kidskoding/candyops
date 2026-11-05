-- One row per allergen and candy a kid with that allergy can eat, under the same rules as the bowls.
select a.allergen, a.candy
from {{ ref('gold_candy_allergens') }} as a
inner join {{ ref('gold_candy_profile') }} as p on p.candy = a.candy
where a.vintage = 'snapshot_2017'
  and a.status = 'not_listed'
  and a.n_evidence >= {{ var('min_evidence') }}
  and not (a.allergen in ('peanut', 'tree_nut') and p.peanut_or_almond)
