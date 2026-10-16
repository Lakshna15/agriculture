-- Demand and supply for each region: a cell of latitude and longitude
-- rounded to one decimal place, about 7 miles across. Searches, crop
-- requests and farms are all placed on this same grid by the extract, which
-- never takes a more precise location out of the application database.

with search_activity as (

    select
        region_latitude,
        region_longitude,
        count(*) filter (where event_type = 'SEARCH_PERFORMED') as searches,
        count(*) filter (where event_type = 'NO_SEARCH_RESULT') as no_result_searches
    from {{ ref('stg_events') }}
    where event_type in ('SEARCH_PERFORMED', 'NO_SEARCH_RESULT')
    group by 1, 2

),

request_activity as (

    select
        region_latitude,
        region_longitude,
        count(*) as open_requests,
        count(*) filter (where not is_covered_by_grow_offer) as unmet_requests,
        count(distinct customer_id) filter (where not is_covered_by_grow_offer) as customers_waiting
    from {{ ref('int_open_crop_requests') }}
    group by 1, 2

),

supply as (

    select
        farms.region_latitude,
        farms.region_longitude,
        count(distinct farms.farm_id) as farms,
        count(products.product_id) filter (where products.is_offered_on_snapshot_date) as listings_available
    from {{ ref('stg_farms') }} as farms
    left join {{ ref('stg_products') }} as products
        on farms.farm_id = products.farm_id
    group by 1, 2

),

regions as (

    select region_latitude, region_longitude from search_activity
    union
    select region_latitude, region_longitude from request_activity
    union
    select region_latitude, region_longitude from supply

)

select
    printf('%.1f,%.1f', regions.region_latitude, regions.region_longitude) as region_id,
    regions.region_latitude,
    regions.region_longitude,
    coalesce(search_activity.searches, 0) as searches,
    coalesce(search_activity.no_result_searches, 0) as no_result_searches,
    coalesce(request_activity.open_requests, 0) as open_requests,
    coalesce(request_activity.unmet_requests, 0) as unmet_requests,
    coalesce(request_activity.customers_waiting, 0) as customers_waiting,
    coalesce(supply.farms, 0) as farms,
    coalesce(supply.listings_available, 0) as listings_available,
    coalesce(search_activity.no_result_searches, 0)
        + coalesce(request_activity.unmet_requests, 0) as unmet_demand_signals

from regions
left join search_activity
    on regions.region_latitude = search_activity.region_latitude
    and regions.region_longitude = search_activity.region_longitude
left join request_activity
    on regions.region_latitude = request_activity.region_latitude
    and regions.region_longitude = request_activity.region_longitude
left join supply
    on regions.region_latitude = supply.region_latitude
    and regions.region_longitude = supply.region_longitude
