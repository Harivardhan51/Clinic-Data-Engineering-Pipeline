import subprocess
import sys


class RawLoader:
    """
    Loads generated CSV files into PostgreSQL raw tables.
    """

    def __init__(self, config, logger, database_manager):
        self.config = config
        self.logger = logger
        self.database_manager = database_manager

    def run(self, context):
        """
        Load raw CSV files into PostgreSQL.

        The current PipelineContext batch_id is passed
        to load_raw_data.py.
        """

        self.logger.info(
            f"Starting raw data load "
            f"for batch {context.batch_id}..."
        )

        try:

            # ------------------------------------------------
            # Run existing raw loader script
            # ------------------------------------------------

            result = subprocess.run(
                [
                    sys.executable,
                    "load_raw_data.py",
                    context.batch_id
                ],
                capture_output=True,
                text=True,
                check=True
            )

            # ------------------------------------------------
            # Log standard output
            # ------------------------------------------------

            if result.stdout:
                for line in result.stdout.strip().splitlines():

                    if line.strip():
                        self.logger.info(line)

            # ------------------------------------------------
            # Log standard error if present
            # ------------------------------------------------

            if result.stderr:
                for line in result.stderr.strip().splitlines():

                    if line.strip():
                        self.logger.warning(line)

            # ------------------------------------------------
            # Get raw table names from configuration
            # ------------------------------------------------

            tables = self.config.get_tables()

            loaded_tables = [
                tables["raw_patients"],
                tables["raw_providers"],
                tables["raw_appointments"],
                tables["raw_payments"]
            ]

            # ------------------------------------------------
            # Verify that data actually exists
            # ------------------------------------------------

            self.logger.info(
                "Verifying loaded raw tables..."
            )

            table_counts = {}

            for table_name in loaded_tables:

                count = self.database_manager.table_count(
                    table_name
                )

                table_counts[table_name] = count

                self.logger.info(
                    f"{table_name}: {count} rows"
                )

            # ------------------------------------------------
            # Store information in PipelineContext
            # ------------------------------------------------

            context.loaded_tables = loaded_tables

            # ------------------------------------------------
            # Success
            # ------------------------------------------------

            self.logger.info(
                f"Raw data load completed successfully "
                f"for batch {context.batch_id}."
            )

            return table_counts

        except subprocess.CalledProcessError as error:

            self.logger.error(
                "Raw data loading script failed."
            )

            if error.stdout:
                self.logger.error(
                    error.stdout
                )

            if error.stderr:
                self.logger.error(
                    error.stderr
                )

            raise

        except Exception as error:

            self.logger.error(
                f"Raw loading failed: {error}"
            )

            raise