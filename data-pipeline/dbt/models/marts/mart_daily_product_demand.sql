-- Demand for each product per marketplace day: how often it was shown in
-- search results and how much of it was reserved. Only days with activity
-- appear.

with views as (

    select
        event_date as activity_date,
        product_id,
        count(*) as product_views
    from {{ ref('stg_events') }}
    where event_type = 'PRODUCT_VIEWED'
        and product_id is not null
    group by 1, 2

),

reservations as (

    select
        created_date as activity_date,
        product_id,
        count(*) as reservations,
        sum(quantity) as units_reserved,
        count(*) filter (where status = 'CANCELLED') as cancelled_reservations
    from {{ ref('stg_product_reservations') }}
    group by 1, 2

),

daily_activity as (

    select
        coalesce(views.activity_date, reservations.activity_date) as activity_date,
        coalesce(views.product_id, reservations.product_id) as product_id,
        coalesce(views.product_views, 0) as product_views,
        coalesce(reservations.reservations, 0) as reservations,
        coalesce(reservations.units_reserved, 0) as units_reserved,
        coalesce(reservations.cancelled_reservations, 0) as cancelled_reservations
    from views
    full outer join reservations
        on views.activity_date = reservations.activity_date
        and views.product_id = reservations.product_id

)

select
    daily_activity.activity_date,
    daily_activity.product_id,
    products.farm_id,
    products.product_name,
    products.category,
    products.unit,
    daily_activity.product_views,
    daily_activity.reservations,
    daily_activity.units_reserved,
    daily_activity.cancelled_reservations,
    -- Reservations per view. It can exceed 1 when reservations come from
    -- somewhere other than a search, so it is a signal, not a probability.
    case
        when daily_activity.product_views > 0
            then round(daily_activity.reservations / daily_activity.product_views, 4)
    end as reservations_per_view

from daily_activity
inner join {{ ref('stg_products') }} as products
    on daily_activity.product_id = products.product_id
