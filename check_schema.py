from src.config.config_manager import ConfigManager
from src.database.database_manager import DatabaseManager


config = ConfigManager()
db = DatabaseManager(config)

tables = [
    "locations",
    "patients",
    "providers",
    "procedure_types",
    "appointments",
    "insurance_payers",
    "claims",
    "payments",
]

connection = db.connect()

try:

    with connection.cursor() as cursor:

        for table in tables:

            print()
            print("=" * 80)
            print(f"CORE.{table.upper()}")
            print("=" * 80)

            cursor.execute(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,)
            )

            rows = cursor.fetchall()

            if not rows:
                print("TABLE NOT FOUND")
                continue

            for column_name, data_type, nullable in rows:

                print(
                    f"{column_name:<35} | "
                    f"{data_type:<30} | "
                    f"nullable={nullable}"
                )

finally:

    db.close()