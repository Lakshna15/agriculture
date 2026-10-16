-- Every change to a product's stock: opening stock, farmer updates,
-- reservations taking stock and cancellations returning it.

select
    id as inventory_change_id,
    product_id,
    previous_quantity,
    new_quantity,
    new_quantity - previous_quantity as quantity_change,
    changed_at,
    {{ marketplace_date('changed_at') }} as change_date

from {{ source('raw', 'inventory_history') }}
