-- Every ranked candy has a matching rule, so a missing match means missing data, not a forgotten rule.
select r.candy
from {{ ref('silver_candy_ranking') }} as r
left anti join {{ ref('candy_aliases') }} as a on a.competitorname = r.candy
where r.is_candy
