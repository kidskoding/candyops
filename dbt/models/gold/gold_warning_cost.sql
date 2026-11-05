-- "May contain" warnings are voluntary, so accepting them prices the labeling choice, not the recipe.
with with_warnings as (
    {{ eligible_candies(['not_listed', 'may_contain']) }}
),

warnings_ranked as (
    select
        *,
        row_number() over (partition by restriction order by win_percent desc, candy) as bowl_rank,
        count(*) over (partition by restriction) as n_eligible
    from with_warnings
),

warnings_bowl as (
    select * from warnings_ranked where bowl_rank <= {{ var('bowl_size') }}
),

strict_summary as (
    select restriction, max(n_eligible) as candies_allowed, avg(win_percent) as avg_win_percent
    from {{ ref('gold_bowls') }}
    group by restriction
),

warnings_summary as (
    select
        w.restriction,
        max(w.n_eligible) as candies_allowed,
        avg(w.win_percent) as avg_win_percent,
        array_join(transform(array_sort(collect_list(case when s.candy is null then struct(w.bowl_rank, w.candy) end)),
                             x -> x.candy), ', ') as added_candies
    from warnings_bowl as w
    left join {{ ref('gold_bowls') }} as s on s.restriction = w.restriction and s.candy = w.candy
    group by w.restriction
),

best as (
    select avg_win_percent from strict_summary where restriction = 'no_restriction'
)

select
    s.restriction,
    s.candies_allowed as candies_allowed_strict,
    w.candies_allowed as candies_allowed_with_warnings,
    round(100 * s.avg_win_percent / best.avg_win_percent, 1) as popularity_kept_strict_pct,
    round(100 * w.avg_win_percent / best.avg_win_percent, 1) as popularity_kept_with_warnings_pct,
    round(100 * (w.avg_win_percent - s.avg_win_percent) / best.avg_win_percent, 1) as warning_cost_pct,
    nullif(w.added_candies, '') as added_candies
from strict_summary as s
inner join warnings_summary as w on w.restriction = s.restriction
cross join best
where s.restriction <> 'no_restriction'
