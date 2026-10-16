-- How each grow offer converted interest into commitments: whether it
-- reached the number of customers it needed, how long that took, and how
-- many of the customers who committed had asked for the crop beforehand.

with numbered_commitments as (

    select
        *,
        row_number() over (
            partition by grow_offer_id
            order by created_at, crop_commitment_id
        ) as commitment_number
    from {{ ref('stg_crop_commitments') }}

),

progress as (

    select
        grow_offer_id,
        count(*) as committed_customers,
        sum(quantity) as committed_quantity
    from numbered_commitments
    group by 1

),

committed_after_requesting as (

    select
        commitments.grow_offer_id,
        count(distinct commitments.customer_id) as customers_who_requested_first
    from numbered_commitments as commitments
    inner join {{ ref('stg_grow_offers') }} as offers
        on commitments.grow_offer_id = offers.grow_offer_id
    inner join {{ ref('stg_crop_requests') }} as requests
        on requests.customer_id = commitments.customer_id
        and requests.crop_name = offers.crop_name
        and requests.created_at <= commitments.created_at
    group by 1

)

select
    offers.grow_offer_id,
    offers.farm_id,
    offers.crop_name,
    offers.status,
    offers.created_at,
    offers.minimum_customers,
    offers.expected_quantity,
    offers.unit,
    coalesce(progress.committed_customers, 0) as committed_customers,
    coalesce(progress.committed_quantity, 0) as committed_quantity,
    -- Commitments cannot be withdrawn, so an offer that once had enough
    -- customers still has them, even if the farmer later cancelled it.
    coalesce(progress.committed_customers, 0) >= offers.minimum_customers as reached_minimum,
    -- The commitment that brought the count up to the minimum.
    threshold.created_at as minimum_reached_at,
    round(date_diff('second', offers.created_at, threshold.created_at) / 86400, 2) as days_to_reach_minimum,
    round(coalesce(progress.committed_quantity, 0) / offers.expected_quantity, 4) as share_of_harvest_committed,
    coalesce(committed_after_requesting.customers_who_requested_first, 0) as customers_who_requested_first

from {{ ref('stg_grow_offers') }} as offers
left join progress
    on offers.grow_offer_id = progress.grow_offer_id
left join numbered_commitments as threshold
    on offers.grow_offer_id = threshold.grow_offer_id
    and threshold.commitment_number = offers.minimum_customers
left join committed_after_requesting
    on offers.grow_offer_id = committed_after_requesting.grow_offer_id
