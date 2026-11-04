-- The CSV's apostrophes arrive as "Õ" (Mac Roman bytes decoded as Latin-1): "HersheyÕs Kisses".
select
    replace(competitorname, 'Õ', "'") as candy,
    competitorname as candy_raw,
    cast(winpercent as double) as win_percent,
    cast(sugarpercent as double) as sugar_percentile,
    cast(pricepercent as double) as price_percentile,
    cast(chocolate as int) = 1 as chocolate,
    cast(fruity as int) = 1 as fruity,
    cast(caramel as int) = 1 as caramel,
    cast(peanutyalmondy as int) = 1 as peanut_or_almond,
    cast(nougat as int) = 1 as nougat,
    cast(crispedricewafer as int) = 1 as crisped_rice_wafer,
    cast(hard as int) = 1 as hard,
    cast(bar as int) = 1 as bar,
    cast(pluribus as int) = 1 as many_per_bag,
    competitorname not in ('One dime', 'One quarter') as is_candy
from {{ source('bronze', 'bronze_candy_ranking') }}
