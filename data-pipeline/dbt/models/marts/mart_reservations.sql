-- Product reservations and farm experience bookings in one table, one row
-- per reservation. Ids are only unique within each kind, so reservation_key
-- combines the kind and the id.

with product_reservations as (

    select
        'PRODUCT' as reservation_type,
        reservations.reservation_id,
        products.farm_id,
        reservations.customer_id,
        reservations.product_id,
        cast(null as bigint) as farm_event_id,
        reservations.quantity,
        reservations.status,
        reservations.created_at,
        reservations.created_date,
        reservations.pickup_date as scheduled_date,
        -- At the product's current price; the price at the time is not recorded.
        reservations.quantity * products.price as estimated_value
    from {{ ref('stg_product_reservations') }} as reservations
    inner join {{ ref('stg_products') }} as products
        on reservations.product_id = products.product_id

),

event_reservations as (

    select
        'EVENT' as reservation_type,
        bookings.event_reservation_id as reservation_id,
        events.farm_id,
        bookings.customer_id,
        cast(null as bigint) as product_id,
        bookings.farm_event_id,
        bookings.party_size as quantity,
        bookings.status,
        bookings.created_at,
        bookings.created_date,
        events.event_date as scheduled_date,
        bookings.party_size * events.price_per_person as estimated_value
    from {{ ref('stg_event_reservations') }} as bookings
    inner join {{ ref('stg_farm_events') }} as events
        on bookings.farm_event_id = events.farm_event_id

),

all_reservations as (

    select * from product_reservations
    union all
    select * from event_reservations

)

select
    lower(reservation_type) || '-' || reservation_id as reservation_key,
    *,
    date_diff('day', created_date, scheduled_date) as lead_time_days,
    status = 'CANCELLED' as is_cancelled

from all_reservations
