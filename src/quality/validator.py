from pathlib import Path
import subprocess
import sys


class Validator:
    """
    Runs validation against the generated raw CSV files.
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        self.processed_path = Path(
            self.config.get_nested("paths", "processed_data")
        )

    def run(self, context):
        """
        Validate generated raw data.
        """

        self.logger.info("Starting data validation...")

        try:
            self.processed_path.mkdir(
                parents=True,
                exist_ok=True
            )

            result = subprocess.run(
                [sys.executable, "validate_data.py"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout:
                self.logger.info(result.stdout.strip())

            validation_report = (
                self.processed_path / "validation_report.csv"
            )

            if not validation_report.exists():
                raise FileNotFoundError(
                    f"Validation report not found: {validation_report}"
                )

            context.validation_report = str(validation_report)

            self.logger.info(
                f"Validation completed successfully: "
                f"{validation_report}"
            )

            return str(validation_report)

        except subprocess.CalledProcessError as error:
            self.logger.error(
                "Validation process failed."
            )

            if error.stdout:
                self.logger.error(error.stdout)

            if error.stderr:
                self.logger.error(error.stderr)

            raise

        except Exception as error:
            self.logger.error(
                f"Validation failed: {error}"
            )
            raise