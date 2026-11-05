with eligible as (
    {{ eligible_candies(['not_listed']) }}
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
