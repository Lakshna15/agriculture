select
    id as product_id,
    farm_id,
    name as product_name,
    category,
    unit,
    price,
    quantity_available,
    organic as is_organic,
    active as is_active,
    harvest_date,
    available_from,
    available_until,
    -- Whether a customer searching on the snapshot date could find and
    -- reserve it, by the same rule the product search applies.
    (
        active
        and quantity_available > 0
        and (available_from is null or available_from <= {{ snapshot_date() }})
        and (available_until is null or available_until >= {{ snapshot_date() }})
    ) as is_offered_on_snapshot_date,
    created_at,
    updated_at

from {{ source('raw', 'products') }}
