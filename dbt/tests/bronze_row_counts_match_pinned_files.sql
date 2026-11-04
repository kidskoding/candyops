-- Splitting the TSV on "\r" as well as "\n" (pandas' default) would give 356,027 rows instead of 356,001.
select 'bronze_off_products' as tbl, count(*) as n from {{ source('bronze', 'bronze_off_products') }} having count(*) <> 356001
union all
select 'bronze_candy_ranking', count(*) from {{ source('bronze', 'bronze_candy_ranking') }} having count(*) <> 85
