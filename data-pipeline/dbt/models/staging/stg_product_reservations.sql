select
    id as reservation_id,
    customer_id,
    product_id,
    quantity,
    pickup_date,
    status,
    created_at,
    {{ marketplace_date('created_at') }} as created_date,
    updated_at

from {{ source('raw', 'product_reservations') }}
