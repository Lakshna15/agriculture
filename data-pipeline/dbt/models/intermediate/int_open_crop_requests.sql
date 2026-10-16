-- Open crop requests, each marked with whether it is already being met: its
-- customer has joined an active grow offer for the same crop. The rule
-- matches the application's local-demand endpoint, which leaves covered
-- requests out of the demand farmers see.

with active_offer_customers as (

    select distinct
        commitments.customer_id,
        offers.crop_name
    from {{ ref('stg_crop_commitments') }} as commitments
    inner join {{ ref('stg_grow_offers') }} as offers
        on commitments.grow_offer_id = offers.grow_offer_id
    where offers.status in {{ active_grow_offer_statuses() }}

)

select
    requests.*,
    active_offer_customers.customer_id is not null as is_covered_by_grow_offer

from {{ ref('stg_crop_requests') }} as requests
left join active_offer_customers
    on requests.customer_id = active_offer_customers.customer_id
    and requests.crop_name = active_offer_customers.crop_name
where requests.status = 'OPEN'
