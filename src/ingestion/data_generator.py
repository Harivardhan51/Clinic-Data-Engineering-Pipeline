from pathlib import Path
import subprocess
import sys


class DataGenerator:
    """
    Runs the existing sample-data generation process.
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        self.raw_data_path = Path(
            self.config.get_nested("paths", "raw_data")
        )

    def run(self, context):
        """
        Generate all raw CSV files.
        """

        self.logger.info("Starting data generation...")

        try:
            # Make sure raw directory exists
            self.raw_data_path.mkdir(parents=True, exist_ok=True)

            # Run existing generator script
            result = subprocess.run(
                [sys.executable, "generate_sample_data.py"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout:
                self.logger.info(result.stdout.strip())

            # Record generated files
            expected_files = [
                "patients.csv",
                "providers.csv",
                "appointments.csv",
                "payments.csv"
            ]

            generated_files = []

            for filename in expected_files:
                file_path = self.raw_data_path / filename

                if file_path.exists():
                    generated_files.append(str(file_path))
                else:
                    raise FileNotFoundError(
                        f"Expected generated file not found: {file_path}"
                    )

            context.generated_files = generated_files

            self.logger.info(
                f"Data generation completed. "
                f"Files generated: {len(generated_files)}"
            )

            return generated_files

        except Exception as error:
            self.logger.error(
                f"Data generation failed: {error}"
            )
            raise