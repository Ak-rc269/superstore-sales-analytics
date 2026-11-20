-- Run after: python run_pipeline.py --skip-publish
-- Counts reflect order lines, distinct orders and distinct customers separately.
SELECT COUNT(*) AS raw_rows FROM raw_data.superstore;

SELECT COUNT(*) AS order_lines,
       COUNT(DISTINCT order_id) AS orders,
       COUNT(DISTINCT customer_id) AS customers,
       MIN(order_date) AS first_order_date,
       MAX(order_date) AS last_order_date,
       SUM(quantity) AS units,
       SUM(sales) AS sales,
       SUM(profit) AS profit,
       SUM(profit) / NULLIF(SUM(sales), 0) AS profit_margin
FROM production.sales_detail;

-- Expected for the uploaded snapshot: 9994 lines, 5009 orders, 793 customers,
-- sales 2297200.8603, profit 286397.0217, units 37873.
-- Amounts use the source file's units; the CSV contains no currency code.

SELECT COUNT(*) AS loss_lines, SUM(profit) AS loss_amount
FROM production.sales_detail WHERE profit < 0;
-- Expected: 1871 lines. Negative profit is retained, not a cleaning error.

SELECT 'detail' AS source_table, SUM(sales) AS sales, SUM(profit) AS profit
FROM production.sales_detail
UNION ALL SELECT 'monthly', SUM(sales), SUM(profit) FROM production.monthly_summary
UNION ALL SELECT 'subcategory', SUM(sales), SUM(profit) FROM production.subcategory_summary
UNION ALL SELECT 'region', SUM(sales), SUM(profit) FROM production.region_summary
UNION ALL SELECT 'segment', SUM(sales), SUM(profit) FROM production.segment_summary
UNION ALL SELECT 'discount', SUM(sales), SUM(profit) FROM production.discount_summary;
-- Sales/profit must reconcile. Do not sum distinct order_count across groups:
-- one order can contain products in several categories or discount bands.

SELECT row_id, order_id, product_id, sales, profit
FROM production.sales_detail WHERE row_id IN ('3406', '3407');
-- These matching business lines have different Row IDs and remain in the data.
