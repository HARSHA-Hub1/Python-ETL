import json
import logging
from pathlib import Path

import pandas as pd

from config.config import get_db_config
from db.db import connect_to_db, create_table, load_data


# --------------------------------------------------
# Logging configuration
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Extract
# --------------------------------------------------

def extract_json(file_path):
    logger.info(f"Reading JSON file: {file_path}")

    with open(file_path, "r") as file:
        data = json.load(file)

    logger.info("JSON extraction successful")

    return data


# --------------------------------------------------
# Flatten
# --------------------------------------------------

def flatten_orders(json_data):

    orders = json_data["orders"]

    logger.info(f"Orders received: {len(orders)}")

    df = pd.json_normalize(
        orders,
        record_path="items",
        meta=[
            "order_id",
            ["customer", "id"],
            ["customer", "name"],
            "order_date",
            "status"
        ]
    )

    logger.info(f"Flattening successful: {len(df)} order-item rows")

    return df


# --------------------------------------------------
# Normalize
# --------------------------------------------------

def normalize_data(df):

    df = df.copy()

    df = df.rename(
        columns={
            "customer.id": "customer_id",
            "customer.name": "customer_name"
        }
    )

    string_columns = [
        "product",
        "order_id",
        "customer_id",
        "customer_name",
        "status"
    ]

    df[string_columns] = df[string_columns].astype("string")

    df["order_date"] = pd.to_datetime(df["order_date"])

    df["unit_price"] = df["unit_price"].astype("float")

    df["status"] = (
        df["status"]
        .str.strip()
        .str.upper()
    )

    logger.info("Data normalization successful")

    return df


# --------------------------------------------------
# Data Quality Validation
# --------------------------------------------------

def validate_data_quality(df):

    valid_status = [
        "COMPLETED",
        "PENDING",
        "CANCELLED"
    ]

    invalid_quantity = df["quantity"] <= 0

    invalid_price = df["unit_price"] <= 0

    invalid_status = ~df["status"].isin(valid_status)

    invalid_null = df.isna().any(axis=1)

    invalid_duplicate = df.duplicated(keep=False)

    invalid_rows = (
        invalid_quantity
        | invalid_price
        | invalid_status
        | invalid_null
        | invalid_duplicate
    )

    rejected_df = df[invalid_rows].copy()

    rejected_df["rejection_reason"] = ""

    rejected_df.loc[
        rejected_df["quantity"] <= 0,
        "rejection_reason"
    ] += "Invalid quantity; "

    rejected_df.loc[
        rejected_df["unit_price"] <= 0,
        "rejection_reason"
    ] += "Invalid price; "

    rejected_df.loc[
        ~rejected_df["status"].isin(valid_status),
        "rejection_reason"
    ] += "Invalid status; "

    rejected_df.loc[
        rejected_df.isna().any(axis=1),
        "rejection_reason"
    ] += "Missing value; "

    rejected_df.loc[
        rejected_df.duplicated(keep=False),
        "rejection_reason"
    ] += "Duplicate row; "

    valid_df = df[~invalid_rows].copy()

    logger.info(f"Valid rows: {len(valid_df)}")
    logger.info(f"Rejected rows: {len(rejected_df)}")

    return valid_df, rejected_df


# --------------------------------------------------
# Transform
# --------------------------------------------------

def transform_data(valid_df):

    df = valid_df.copy()

    df["total_amount"] = (
        df["quantity"] * df["unit_price"]
    )

    df["order_category"] = df["status"].map({
        "COMPLETED": "SALE",
        "PENDING": "PENDING_ORDER",
        "CANCELLED": "CANCELLED_ORDER"
    })

    target_columns = [
        "order_id",
        "customer_id",
        "customer_name",
        "order_date",
        "status",
        "order_category",
        "product",
        "quantity",
        "unit_price",
        "total_amount"
    ]

    final_df = df[target_columns].copy()

    final_df["order_category"] = (
        final_df["order_category"].astype("string")
    )

    logger.info("Data transformation successful")

    return final_df


# --------------------------------------------------
# Final Validation
# --------------------------------------------------

def final_validation(final_df):

    logger.info("Starting final validation")

    null_count = final_df.isna().sum().sum()

    duplicate_count = final_df.duplicated().sum()

    amount_mismatch_count = (
        final_df["total_amount"]
        != final_df["quantity"] * final_df["unit_price"]
    ).sum()

    logger.info(f"Final rows: {len(final_df)}")
    logger.info(f"Null values: {null_count}")
    logger.info(f"Duplicate rows: {duplicate_count}")
    logger.info(
        f"Total amount mismatches: {amount_mismatch_count}"
    )

    if (
        null_count > 0
        or duplicate_count > 0
        or amount_mismatch_count > 0
    ):
        raise ValueError(
            "Final validation failed"
        )

    logger.info("Final validation successful")


# --------------------------------------------------
# Main ETL
# --------------------------------------------------

def main():

    logger.info("========== ETL STARTED ==========")

    try:

        # File path
        input_file = Path("data/orders.json")

        # Extract
        json_data = extract_json(input_file)

        # Flatten
        df = flatten_orders(json_data)

        # Normalize
        df = normalize_data(df)

        # Validate
        valid_df, rejected_df = validate_data_quality(df)

        # Transform
        final_df = transform_data(valid_df)

        # Final validation
        final_validation(final_df)

        # Save clean data
        final_df.to_csv(
            "data/clean_orders.csv",
            index=False
        )

        logger.info(
            "Clean data saved to data/clean_orders.csv"
        )

        # Save rejected data if any
        if not rejected_df.empty:

            rejected_df.to_csv(
                "data/rejected_orders.csv",
                index=False
            )

            logger.info(
                "Rejected data saved to "
                "data/rejected_orders.csv"
            )

        # Database
        db_config = get_db_config()

        conn = connect_to_db(**db_config)

        try:

            create_table(
                conn,
                "orders"
            )

            load_data(
                conn,
                final_df
            )

        finally:

            conn.close()

            logger.info(
                "Database connection closed"
            )

        logger.info("========== ETL COMPLETED ==========")

    except Exception:

        logger.exception(
            "ETL pipeline failed"
        )

        raise


if __name__ == "__main__":
    main()
