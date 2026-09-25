import psycopg2
import logging
from psycopg2 import sql

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger=logging.getLogger(__name__)
def connect_to_db(**kwargs):
    try:
        conn=psycopg2.connect(**kwargs)
        logger.info("Database connection successful")
        return conn
    except Exception:
        logger.exception(f"Error connecting to PostgreSQL")
        raise

def create_table(conn,table_name):
    query= sql.SQL("""
        CREATE TABLE IF NOT EXISTS {table_name} (
            order_item_id SERIAL PRIMARY KEY,
            order_id VARCHAR(20),
            customer_id VARCHAR(20),
            customer_name VARCHAR(100),
            order_date DATE,
            status VARCHAR(20),
            order_category VARCHAR(30),
            product VARCHAR(100),
            quantity INTEGER,
            unit_price NUMERIC(12, 2),
            total_amount NUMERIC(14, 2)
        )
    """).format(table_name=sql.Identifier(table_name))
    cur=None
    try:
        logger.info(f"Creating table: {table_name}")
        cur=conn.cursor()
        cur.execute(query)
        conn.commit()
        logger.info("Table created/verified successfully: orders")
    except Exception:
        conn.rollback()
        logger.exception(f"Error creating table: {table_name}")
        raise
    finally:
        if cur:
            logger.info(f"Closing Cursor to Postgres")
            cur.close()

def load_data(conn, df):
    cursor=None
    try:
        logger.info(f"Loading data into PostgreSQL")
        cursor = conn.cursor()

        query = """
            INSERT INTO orders (
                order_id,
                customer_id,
                customer_name,
                order_date,
                status,
                order_category,
                product,
                quantity,
                unit_price,
                total_amount
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        inserted_rows=0
        for row in df.itertuples(index=False,name=None):
            cursor.execute(query, row)
            inserted_rows += 1

        conn.commit()
        logger.info(f"Input rows:{len(df)}")
        logger.info(f"Inserted rows:{inserted_rows}")
        logger.info(f"Not inserted rows:{len(df)-inserted_rows}")
    except Exception:
        conn.rollback()
        logger.exception(f"Error loading data")
        raise
    finally:
        if cursor:
            cursor.close()