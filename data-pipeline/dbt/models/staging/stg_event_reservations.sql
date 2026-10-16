select
    id as event_reservation_id,
    event_id as farm_event_id,
    customer_id,
    party_size,
    status,
    created_at,
    {{ marketplace_date('created_at') }} as created_date

from {{ source('raw', 'event_reservations') }}
