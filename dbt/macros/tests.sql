{% test value_between(model, column_name, min, max) %}
select * from {{ model }} where {{ column_name }} < {{ min }} or {{ column_name }} > {{ max }}
{% endtest %}

{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
