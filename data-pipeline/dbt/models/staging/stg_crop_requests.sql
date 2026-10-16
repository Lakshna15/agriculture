select
    id as crop_request_id,
    customer_id,
    crop_name,
    quantity,
    unit,
    frequency,
    radius_miles,
    preferred_season,
    status,
    region_latitude,
    region_longitude,
    created_at

from {{ source('raw', 'crop_requests') }}
