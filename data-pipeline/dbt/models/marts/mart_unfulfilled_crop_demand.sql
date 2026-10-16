-- Demand and supply for each crop customers have searched for or requested.
--
-- Demand comes from searches (and the share that found nothing) and from
-- open crop requests not yet met by a grow offer. Supply is the listings a
-- customer could reserve on the snapshot date whose name contains the crop,
-- the same name match the product search uses, and the grow offers in
-- progress. Search terms and crop names share one spelling, each word
-- capitalized, so "okra" searches and "Okra" requests count together.

with searches as (

    select
        search_term as crop_name,
        count(*) filter (where event_type = 'SEARCH_PERFORMED') as searches,
        count(*) filter (where event_type = 'NO_SEARCH_RESULT') as no_result_searches
    from {{ ref('stg_events') }}
    where event_type in ('SEARCH_PERFORMED', 'NO_SEARCH_RESULT')
        and search_term is not null
    group by 1

),

requests as (

    select
        crop_name,
        count(*) as open_requests,
        count(*) filter (where not is_covered_by_grow_offer) as unmet_requests,
        count(distinct customer_id) filter (where not is_covered_by_grow_offer) as customers_waiting
    from {{ ref('int_open_crop_requests') }}
    group by 1

),

grow_offers as (

    select
        crop_name,
        count(*) as active_grow_offers
    from {{ ref('stg_grow_offers') }}
    where status in {{ active_grow_offer_statuses() }}
    group by 1

),

crops as (

    select crop_name from searches
    union
    select crop_name from requests

),

listings as (

    select
        crops.crop_name,
        count(products.product_id) as listings_available
    from crops
    left join {{ ref('stg_products') }} as products
        on products.is_offered_on_snapshot_date
        and contains(lower(products.product_name), lower(crops.crop_name))
    group by 1

),

combined as (

    select
        crops.crop_name,
        coalesce(searches.searches, 0) as searches,
        coalesce(searches.no_result_searches, 0) as no_result_searches,
        coalesce(requests.open_requests, 0) as open_requests,
        coalesce(requests.unmet_requests, 0) as unmet_requests,
        coalesce(requests.customers_waiting, 0) as customers_waiting,
        coalesce(grow_offers.active_grow_offers, 0) as active_grow_offers,
        listings.listings_available
    from crops
    left join searches on crops.crop_name = searches.crop_name
    left join requests on crops.crop_name = requests.crop_name
    left join grow_offers on crops.crop_name = grow_offers.crop_name
    inner join listings on crops.crop_name = listings.crop_name

)

select
    *,
    case when searches > 0 then round(no_result_searches / searches, 4) end as no_result_rate,
    no_result_searches + unmet_requests as unmet_demand_signals,
    -- Demand for each listing that could meet it. One is added to the
    -- listings so a crop with none still compares by the size of its demand
    -- rather than dividing by zero.
    round((searches + customers_waiting) / (listings_available + 1), 2) as demand_per_listing

from combined
