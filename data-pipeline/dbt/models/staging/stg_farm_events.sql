select
    id as farm_event_id,
    farm_id,
    event_type,
    event_date,
    price as price_per_person,
    capacity,
    created_at

from {{ source('raw', 'farm_events') }}
