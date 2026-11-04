with bowls as (
    select
        restriction,
        max(n_eligible) as candies_allowed,
        count(*) as bowl_size,
        avg(win_percent) as avg_win_percent,
        median(sugars_100g) as median_sugars_100g,
        array_join(transform(array_sort(collect_list(struct(bowl_rank, candy))), x -> x.candy), ', ') as bowl
    from {{ ref('gold_bowls') }}
    group by restriction
)

select
    b.restriction,
    b.candies_allowed,
    b.bowl_size,
    round(b.avg_win_percent, 2) as avg_win_percent,
    round(100 * b.avg_win_percent / best.avg_win_percent, 1) as popularity_kept_pct,
    round(b.median_sugars_100g, 1) as median_sugars_100g,
    b.bowl
from bowls as b
cross join (select avg_win_percent from bowls where restriction = 'no_restriction') as best
