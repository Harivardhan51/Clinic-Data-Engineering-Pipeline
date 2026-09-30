import logging
from pathlib import Path


class PipelineLogger:
    """
    Centralized logger for the entire data pipeline.
    """

    def __init__(self, log_directory="logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("clinic_pipeline")

        # Prevent duplicate handlers if logger is initialized multiple times
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            # File handler
            file_handler = logging.FileHandler(
                self.log_directory / "pipeline.log",
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)

            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)

    def exception(self, message):
        self.logger.exception(message)