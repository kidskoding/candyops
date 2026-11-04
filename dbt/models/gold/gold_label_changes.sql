-- Is the 2017 answer still true? Each candy's allergen status in the 2017 snapshot next to its status in the
-- products edited since the change feed started. Only candies with enough current evidence can show a change.
with s as (
    select * from {{ ref('gold_candy_allergens') }} where vintage = 'snapshot_2017'
),

f as (
    select * from {{ ref('gold_candy_allergens') }} where vintage = 'change_feed'
)

select
    s.candy,
    s.allergen,
    s.status as status_2017,
    s.n_evidence as evidence_2017,
    f.status as status_now,
    f.n_evidence as evidence_now,
    f.evidence_scope as scope_now,
    case
        when f.n_evidence < {{ var('min_evidence') }} then 'not_enough_current_data'
        when s.n_evidence < {{ var('min_evidence') }} then 'newly_covered'
        when s.status = f.status then 'unchanged'
        else 'changed'
    end as comparison
from s
inner join f on f.candy = s.candy and f.allergen = s.allergen
