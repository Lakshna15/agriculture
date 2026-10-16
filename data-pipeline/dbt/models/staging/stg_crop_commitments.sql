select
    id as crop_commitment_id,
    grow_offer_id,
    customer_id,
    quantity,
    created_at

from {{ source('raw', 'crop_commitments') }}
