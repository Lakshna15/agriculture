select
    id as grow_offer_id,
    farm_id,
    crop_name,
    expected_quantity,
    unit,
    estimated_price,
    planting_date,
    expected_harvest_date,
    minimum_customers,
    status,
    created_at

from {{ source('raw', 'grow_offers') }}
