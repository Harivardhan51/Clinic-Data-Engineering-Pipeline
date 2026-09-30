from datetime import datetime


class PipelineContext:
    """
    Stores information shared across the entire pipeline run.
    """

    def __init__(self):
        self.batch_id = self._generate_batch_id()

        self.start_time = datetime.now()
        self.end_time = None

        self.status = "STARTED"

        self.generated_files = []
        self.validation_report = None
        self.loaded_tables = []
        self.transformed_tables = []
        self.quality_report = None
        self.final_report = None

    def _generate_batch_id(self):
        """
        Generate a unique batch ID for the current pipeline execution.
        """
        return datetime.now().strftime("BATCH_%Y%m%d_%H%M%S")

    def mark_completed(self):
        """
        Mark the pipeline as successfully completed.
        """
        self.end_time = datetime.now()
        self.status = "COMPLETED"

    def mark_failed(self):
        """
        Mark the pipeline as failed.
        """
        self.end_time = datetime.now()
        self.status = "FAILED"

    def get_duration_seconds(self):
        """
        Return pipeline execution duration in seconds.
        """
        if self.end_time is None:
            return None

        return (self.end_time - self.start_time).total_seconds()

    def summary(self):
        """
        Return a summary of the current pipeline execution.
        """
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.get_duration_seconds(),
            "generated_files": self.generated_files,
            "validation_report": self.validation_report,
            "loaded_tables": self.loaded_tables,
            "transformed_tables": self.transformed_tables,
            "quality_report": self.quality_report,
            "final_report": self.final_report,
        }