# Order ETL

This is a small Python pipeline that takes nested order JSON, flattens it to one row per line item, drops anything that fails a few basic checks, and loads the clean rows into PostgreSQL. A CSV of the same clean data is written next to the source file so you can look at the result without opening the database.

The sample file, `data/orders.json`, has 20 orders from August 2026. Some orders have more than one product, so the output is wider than the order count. A laptop and a mouse on the same order become two rows.

## What the pipeline does

`etl.py` runs the steps in this order:

1. **Extract.** Read `data/orders.json`.
2. **Flatten.** Each item inside an order becomes its own row. Customer id, customer name, order date, and status are copied onto every item from that order.
3. **Normalize.** Column names are cleaned up (`customer.id` becomes `customer_id`), strings and dates are typed, prices are floats, and status is trimmed and uppercased.
4. **Validate.** Bad rows are split out. Good rows stay in the pipeline.
5. **Transform.** `total_amount` is `quantity * unit_price`. Status is also mapped to a category: `COMPLETED` becomes `SALE`, `PENDING` becomes `PENDING_ORDER`, and `CANCELLED` becomes `CANCELLED_ORDER`.
6. **Check the result.** If the final frame still has nulls, duplicate rows, or a total that does not match quantity times price, the job stops and nothing is loaded.
7. **Write files and load.** Clean rows go to `data/clean_orders.csv`. Rejected rows, if there are any, go to `data/rejected_orders.csv` with a `rejection_reason` column. Then the clean rows are inserted into the `orders` table.

If something blows up, the error is logged and the exception is raised again, so the process exits with a failure instead of pretending it finished.

## What gets rejected

A row is kept only if all of these are true:

- quantity is greater than 0
- unit price is greater than 0
- status is `COMPLETED`, `PENDING`, or `CANCELLED`
- no column is null
- the row is not a duplicate of another row

A rejected row can fail more than one of these. The reasons are concatenated in `rejection_reason`, for example `Invalid quantity; Invalid price; `.

The sample JSON is already clean, so a normal run writes `clean_orders.csv` and does not create `rejected_orders.csv`.

## Project layout

```
etl_project/
├── etl.py              # the pipeline
├── config/config.py    # reads database settings from .env
├── db/db.py            # connect, create the table, insert rows
├── data/orders.json    # source orders
└── data/clean_orders.csv
```

`data/clean_orders.csv` is output from a previous run. It is overwritten every time the job succeeds.

## Setup

You need Python 3 and a running PostgreSQL database. Install the packages the code imports:

```bash
pip install pandas psycopg2-binary python-dotenv
```

Create a `.env` file in the project root. `config/config.py` refuses to start if any of these are missing:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

`.env` is listed in `.gitignore`. Do not commit it.

The database itself has to exist already. The script only creates the table.

## Run it

From the project root:

```bash
python etl.py
```

Paths are relative (`data/orders.json`, `data/clean_orders.csv`), so run it from this folder.

You should see log lines for each step, then `ETL COMPLETED`. On a clean sample run that is 20 orders flattened to 27 item rows, all of them valid.

## The table

`orders` is created with `CREATE TABLE IF NOT EXISTS`. Columns:

| Column | What it holds |
| --- | --- |
| `order_item_id` | serial primary key, assigned by Postgres |
| `order_id` | for example `ORD10001` |
| `customer_id` | for example `C101` |
| `customer_name` | customer name from the JSON |
| `order_date` | date of the order |
| `status` | `COMPLETED`, `PENDING`, or `CANCELLED` |
| `order_category` | `SALE`, `PENDING_ORDER`, or `CANCELLED_ORDER` |
| `product` | line item name |
| `quantity` | units on that line |
| `unit_price` | price per unit |
| `total_amount` | quantity times unit price |

One thing to know before you run it twice: inserts are plain `INSERT`s. The table is not truncated and there is no unique key on `order_id` plus product, so a second successful run adds the same rows again. If you want a fresh load, clear the table first.
