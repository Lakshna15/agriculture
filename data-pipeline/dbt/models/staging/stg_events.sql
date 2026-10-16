-- One row per application event, with the metadata each event type carries
-- unpacked into typed columns. A column is null for event types that do not
-- record that fact.

with source as (

    select * from {{ source('raw', 'application_events') }}

)

select
    id as event_id,
    event_type,
    user_id,
    farm_id,
    product_id,
    created_at,
    {{ marketplace_date('created_at') }} as event_date,

    -- Searches and the listings they showed
    json_extract_string(metadata, '$.search_id') as search_id,
    json_extract_string(metadata, '$.search_term') as search_term,
    json_extract_string(metadata, '$.category') as search_category,
    cast(json_extract_string(metadata, '$.result_count') as integer) as result_count,
    cast(json_extract_string(metadata, '$.region_latitude') as double) as region_latitude,
    cast(json_extract_string(metadata, '$.region_longitude') as double) as region_longitude,
    cast(json_extract_string(metadata, '$.position') as integer) as result_position,
    json_extract_string(metadata, '$.source') as view_source,

    -- Marketplace actions
    json_extract_string(metadata, '$.crop_name') as crop_name,
    cast(json_extract_string(metadata, '$.quantity') as integer) as quantity,
    cast(json_extract_string(metadata, '$.reservation_id') as bigint) as reservation_id,
    cast(json_extract_string(metadata, '$.event_reservation_id') as bigint) as event_reservation_id,
    cast(json_extract_string(metadata, '$.crop_request_id') as bigint) as crop_request_id,
    cast(json_extract_string(metadata, '$.grow_offer_id') as bigint) as grow_offer_id,
    cast(json_extract_string(metadata, '$.crop_commitment_id') as bigint) as crop_commitment_id,
    cast(json_extract_string(metadata, '$.confirmed_offer') as boolean) as confirmed_offer,
    cast(json_extract_string(metadata, '$.previous_quantity') as integer) as previous_quantity,
    cast(json_extract_string(metadata, '$.new_quantity') as integer) as new_quantity,

    metadata

from source
