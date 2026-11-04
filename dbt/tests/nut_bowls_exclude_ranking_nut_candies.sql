-- A candy FiveThirtyEight tags as peanut/almond must never reach a bowl that avoids peanuts or tree nuts.
select b.restriction, b.candy
from {{ ref('gold_bowls') }} as b
inner join {{ ref('restrictions') }} as r on r.restriction = b.restriction and r.allergen in ('peanut', 'tree_nut')
inner join {{ ref('gold_candy_profile') }} as p on p.candy = b.candy and p.peanut_or_almond
