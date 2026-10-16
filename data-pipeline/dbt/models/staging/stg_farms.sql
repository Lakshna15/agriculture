select
    id as farm_id,
    owner_id as farmer_id,
    farm_name,
    city,
    state,
    region_latitude,
    region_longitude,
    pickup_available,
    delivery_available,
    created_at

from {{ source('raw', 'farms') }}
