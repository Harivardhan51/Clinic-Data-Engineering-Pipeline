import sys
from pathlib import Path

import pandas as pd
import psycopg2


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "clinic_db",
    "user": "postgres",
    "password": "harivardhan",
}


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DATA_DIR = BASE_DIR / "data" / "raw"


# ============================================================
# TABLE MAPPING
# ============================================================

TABLE_MAPPING = {
    "patients.csv": "raw.patients_file",
    "providers.csv": "raw.providers_file",
    "appointments.csv": "raw.appointments_file",
    "payments.csv": "raw.payments_file",
}


# ============================================================
# GET BATCH ID
# ============================================================

if len(sys.argv) < 2:
    raise ValueError(
        "batch_id is required.\n"
        "Example:\n"
        "python load_raw_data.py BATCH_20260908_231500"
    )

batch_id = sys.argv[1]


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a PostgreSQL database connection.
    """

    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


# ============================================================
# LOAD ONE CSV INTO ONE RAW TABLE
# ============================================================

def load_csv_to_table(connection, csv_file, table_name, batch_id):
    """
    Read one CSV file and load it into the specified raw table.

    Existing data in the raw table is cleared before loading.
    Every row receives the current pipeline batch_id.
    """

    csv_path = RAW_DATA_DIR / csv_file

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}"
        )

    print(f"Reading: {csv_path}")

    df = pd.read_csv(csv_path)

    print(f"Rows read: {len(df)}")

    # --------------------------------------------------------
    # Add pipeline batch ID
    # --------------------------------------------------------

    df["batch_id"] = batch_id

    # --------------------------------------------------------
    # Convert NaN to None
    # PostgreSQL will store these as NULL
    # --------------------------------------------------------

    df = df.where(pd.notnull(df), None)

    # --------------------------------------------------------
    # Clear existing raw table
    # --------------------------------------------------------

    print(f"Clearing table: {table_name}")

    with connection.cursor() as cursor:
        cursor.execute(
            f"TRUNCATE TABLE {table_name}"
        )

    connection.commit()

    # --------------------------------------------------------
    # Get column names from PostgreSQL table
    # --------------------------------------------------------

    schema_name, table_only = table_name.split(".")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_only),
        )

        database_columns = [
            row[0]
            for row in cursor.fetchall()
        ]

    # --------------------------------------------------------
    # Check that CSV columns match database columns
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in database_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns for {table_name}: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Use only columns that exist in database
    # --------------------------------------------------------

    df = df[database_columns]

    # --------------------------------------------------------
    # Build INSERT statement
    # --------------------------------------------------------

    column_names = ", ".join(
        f'"{column}"'
        for column in database_columns
    )

    placeholders = ", ".join(
        ["%s"] * len(database_columns)
    )

    insert_query = f"""
        INSERT INTO {table_name}
        ({column_names})
        VALUES ({placeholders})
    """

    # --------------------------------------------------------
    # Insert records
    # --------------------------------------------------------

    records = [
        tuple(row)
        for row in df.itertuples(
            index=False,
            name=None
        )
    ]

    print(
        f"Loading {len(records)} rows into {table_name}..."
    )

    with connection.cursor() as cursor:

        cursor.executemany(
            insert_query,
            records
        )

    connection.commit()

    print(
        f"Successfully loaded {len(records)} rows "
        f"into {table_name}"
    )

    return len(records)


# ============================================================
# MAIN LOAD PROCESS
# ============================================================

def main():
    """
    Load all four CSV files into PostgreSQL raw tables.
    """

    print("=" * 60)
    print("RAW DATA LOAD STARTED")
    print("=" * 60)

    print(f"Batch ID: {batch_id}")
    print(f"Raw data directory: {RAW_DATA_DIR}")

    connection = None

    try:

        # ----------------------------------------------------
        # Connect to PostgreSQL
        # ----------------------------------------------------

        print("\nConnecting to PostgreSQL...")

        connection = get_connection()

        print("PostgreSQL connection successful.")

        total_rows = 0

        # ----------------------------------------------------
        # Load each CSV
        # ----------------------------------------------------

        for csv_file, table_name in TABLE_MAPPING.items():

            print("\n" + "-" * 60)

            rows_loaded = load_csv_to_table(
                connection=connection,
                csv_file=csv_file,
                table_name=table_name,
                batch_id=batch_id,
            )

            total_rows += rows_loaded

        # ----------------------------------------------------
        # Verify batch IDs
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("BATCH VERIFICATION")
        print("=" * 60)

        with connection.cursor() as cursor:

            for table_name in TABLE_MAPPING.values():

                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_name}
                    WHERE batch_id = %s
                    """,
                    (batch_id,),
                )

                count = cursor.fetchone()[0]

                print(
                    f"{table_name}: "
                    f"{count} rows for batch {batch_id}"
                )

        print("\n" + "=" * 60)
        print("RAW DATA LOAD COMPLETED")
        print("=" * 60)

        print(f"Total rows loaded: {total_rows}")

    except Exception as error:

        if connection:
            connection.rollback()

        print("\n" + "=" * 60)
        print("RAW DATA LOAD FAILED")
        print("=" * 60)

        print(f"Error: {error}")

        raise

    finally:

        if connection:
            connection.close()

            print(
                "\nPostgreSQL connection closed."
            )


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()