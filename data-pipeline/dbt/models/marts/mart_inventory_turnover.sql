-- How quickly each farm's stock sells, measured in dollars so that pounds,
-- dozens and bunches can be added together.
--
-- Stock is rebuilt day by day from the inventory history: a product's stock
-- on a day is the quantity after its last change on or before that day. A
-- farm is observed from its first stock change to the snapshot date.
-- Reservations that were not cancelled count as sold. Values use each
-- product's current price, because the price at the time is not recorded.

with closing_stock_by_change_day as (

    -- Changes to one product are serialized by a row lock in the application,
    -- so a higher id is always a later change.
    select
        product_id,
        change_date,
        max_by(new_quantity, inventory_change_id) as closing_quantity
    from {{ ref('stg_inventory') }}
    group by 1, 2

),

first_stock_dates as (

    select
        product_id,
        min(change_date) as first_stock_date
    from closing_stock_by_change_day
    group by 1

),

product_days as (

    select
        products.product_id,
        products.farm_id,
        products.price,
        cast(unnest(generate_series(starts.first_stock_date, {{ snapshot_date() }}, interval 1 day)) as date) as stock_date
    from first_stock_dates as starts
    inner join {{ ref('stg_products') }} as products
        on starts.product_id = products.product_id

),

daily_stock as (

    select
        product_days.farm_id,
        product_days.stock_date,
        product_days.price * stock.closing_quantity as stock_value
    from product_days
    asof join closing_stock_by_change_day as stock
        on product_days.product_id = stock.product_id
        and product_days.stock_date >= stock.change_date

),

farm_stock as (

    select
        farm_id,
        count(distinct stock_date) as days_observed,
        sum(stock_value) / count(distinct stock_date) as average_stock_value
    from daily_stock
    group by 1

),

sold as (

    select
        products.farm_id,
        sum(reservations.quantity) as units_sold,
        sum(reservations.quantity * products.price) as sold_value
    from {{ ref('stg_product_reservations') }} as reservations
    inner join {{ ref('stg_products') }} as products
        on reservations.product_id = products.product_id
    where reservations.status <> 'CANCELLED'
    group by 1

)

select
    farms.farm_id,
    farms.farm_name,
    farm_stock.days_observed,
    round(farm_stock.average_stock_value, 2) as average_stock_value,
    coalesce(sold.units_sold, 0) as units_sold,
    coalesce(sold.sold_value, 0) as sold_value,
    -- Times the average stock was sold over the observed days.
    round(coalesce(sold.sold_value, 0) / nullif(farm_stock.average_stock_value, 0), 4) as inventory_turnover,
    -- Days the average stock lasts at the observed rate of sale. Fewer days
    -- is faster turnover; it is empty for a farm that has sold nothing.
    round(
        farm_stock.average_stock_value / nullif(coalesce(sold.sold_value, 0) / farm_stock.days_observed, 0),
        1
    ) as days_of_inventory

from farm_stock
inner join {{ ref('stg_farms') }} as farms
    on farm_stock.farm_id = farms.farm_id
left join sold
    on farm_stock.farm_id = sold.farm_id
