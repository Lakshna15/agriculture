{#
  Dates in the marts are calendar days where the marketplace operates, as in
  the application, not UTC days: a reservation made at 9 pm in Charlotte
  belongs to that day, not the next.
#}
{% macro marketplace_date(timestamp_column) -%}
    cast(timezone('{{ env_var("MARKETPLACE_TIMEZONE", "America/New_York") }}', {{ timestamp_column }}) as date)
{%- endmacro %}

{% macro snapshot_date() -%}
    cast('{{ var("snapshot_date") }}' as date)
{%- endmacro %}

{#
  Grow offers still on their way to a harvest. A customer who has joined one
  for a crop is already being served for it, the same rule the application's
  local-demand endpoint applies.
#}
{% macro active_grow_offer_statuses() -%}
    ('OPEN', 'CONFIRMED', 'GROWING', 'READY')
{%- endmacro %}
