-- Distance: one point per differing FiveThirtyEight trait plus the sugar and price percentile gaps (0 to 1 each).
with traits as (
    select
        candy,
        win_percent,
        sugar_percentile,
        price_percentile,
        array(chocolate, fruity, caramel, peanut_or_almond, nougat, crisped_rice_wafer, hard, bar, many_per_bag)
            as flags
    from {{ ref('silver_candy_ranking') }}
    where is_candy
),

trait_names as (
    select array('chocolate', 'fruity', 'caramel', 'peanut or almond', 'nougat', 'crisped rice or wafer', 'hard',
                 'bar', 'many per bag') as names
),

eligible as (
    {{ eligible_candies(['not_listed']) }}
),

favorites as (
    select b.bowl_rank as favorite_rank, b.candy as favorite
    from {{ ref('gold_bowls') }} as b
    where b.restriction = 'no_restriction'
),

pairs as (
    select
        e.restriction,
        f.favorite_rank,
        f.favorite,
        e.candy as swap,
        tf.win_percent as favorite_win_percent,
        ts.win_percent as swap_win_percent,
        size(filter(sequence(0, 8), i -> tf.flags[i] <> ts.flags[i]))
            + abs(tf.sugar_percentile - ts.sugar_percentile)
            + abs(tf.price_percentile - ts.price_percentile) as distance,
        filter(sequence(0, 8), i -> tf.flags[i] and ts.flags[i]) as shared_idx
    from favorites as f
    inner join traits as tf on tf.candy = f.favorite
    inner join eligible as e on e.restriction <> 'no_restriction'
    inner join traits as ts on ts.candy = e.candy
    left anti join eligible as keep on keep.restriction = e.restriction and keep.candy = f.favorite
),

ranked as (
    select
        *,
        row_number() over (partition by restriction, favorite order by distance, swap_win_percent desc, swap)
            as swap_rank
    from pairs
)

select
    r.restriction,
    r.favorite_rank,
    r.favorite,
    r.swap,
    round(r.distance, 2) as distance,
    array_join(transform(r.shared_idx, i -> n.names[i]), ', ') as shared_traits,
    round(r.favorite_win_percent, 1) as favorite_win_percent,
    round(r.swap_win_percent, 1) as swap_win_percent
from ranked as r
cross join trait_names as n
where r.swap_rank = 1
