{# Trim every kind of whitespace (Spark's trim() only strips spaces; 26 source rows carry a stray "\r"), empty -> null #}
{% macro clean(col) -%}
nullif(regexp_replace({{ col }}, r'^\s+|\s+$', ''), '')
{%- endmacro %}

{# Lowercase, strip accents and apostrophes, collapse whitespace: the form every regex rule is written against #}
{% macro normalize_text(col) -%}
trim(regexp_replace(regexp_replace(
  translate(
    replace(replace(replace(lower({{ col }}), 'œ', 'oe'), 'æ', 'ae'), 'ß', 'ss'),
    'àáâãäåāçćčèéêëēěìíîïīñòóôõöøōùúûüūýÿ',
    'aaaaaaaccceeeeeeiiiiinooooooouuuuuyy'),
  r"['’`´]", ''), r'\s+', ' '))
{%- endmacro %}

{% macro rule(name) -%}
(select pattern from {{ ref('text_rules') }} where rule = '{{ name }}')
{%- endmacro %}
