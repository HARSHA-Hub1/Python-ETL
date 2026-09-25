import os
from dotenv import load_dotenv
import logging
load_dotenv()

def get_db_config():
    required_vars=["DB_HOST","DB_PORT","DB_USER","DB_NAME","DB_PASSWORD"]
    missing_vars=[var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing database environment variables: {missing_vars}"
        )
    return{
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }
