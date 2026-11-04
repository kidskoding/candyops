-- Allergen flags for every matched product, parsed from its ingredient list, allergens field and traces field.
-- Text after "may contain" / "made on shared equipment" counts as may_contain, not contains.
with products as (
    select
        p.code,
        p.ingredients_text is not null as has_ingredients,
        {{ normalize_text('p.ingredients_text') }} as ingredients,
        coalesce({{ normalize_text('p.allergens') }}, '') as allergens,
        coalesce({{ normalize_text('p.traces') }}, '') as traces
    from {{ ref('silver_products') }} as p
    where p.code in (select code from {{ ref('silver_candy_matches') }})
),

split_text as (
    select
        code,
        has_ingredients,
        allergens,
        traces,
        regexp_replace(
            coalesce(try_element_at(split(ingredients, {{ rule('may_contain') }}, 2), 1), ''),
            {{ rule('negation') }}, ' ') as body,
        coalesce(try_element_at(split(ingredients, {{ rule('may_contain') }}, 2), 2), '') as tail
    from products
)

select
    s.code,
    t.allergen,
    s.has_ingredients,
    regexp_replace(s.body, coalesce(t.ignore_regex, '(?!)'), ' ') rlike t.contains_regex
        or regexp_replace(s.allergens, coalesce(t.ignore_regex, '(?!)'), ' ') rlike t.contains_regex as contains,
    s.tail rlike t.contains_regex or s.traces rlike t.contains_regex as may_contain
from split_text as s
cross join {{ ref('allergen_terms') }} as t
