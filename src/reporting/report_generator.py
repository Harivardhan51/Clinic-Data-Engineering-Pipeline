import os
from datetime import datetime

import pandas as pd


class ReportGenerator:
    """
    Generates pipeline quality reports from QualityChecker results.
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        paths = self.config.get_paths()

        self.report_directory = paths.get(
            "reports",
            "data/processed/reports"
        )

        os.makedirs(self.report_directory, exist_ok=True)

    def run(self, context):
        self.logger.info(
            f"Starting report generation for batch {context.batch_id}..."
        )

        quality_result = context.quality_result

        if not quality_result:
            raise ValueError(
                "Quality results are not available. "
                "Run QualityChecker before ReportGenerator."
            )

        checks = quality_result["checks"]

        # ---------------------------------------------------------
        # Detailed check report
        # ---------------------------------------------------------

        details_df = pd.DataFrame(checks)

        detail_file = os.path.join(
            self.report_directory,
            f"quality_report_{context.batch_id}.csv"
        )

        details_df.to_csv(
            detail_file,
            index=False
        )

        # ---------------------------------------------------------
        # Summary report
        # ---------------------------------------------------------

        summary = {
            "batch_id": context.batch_id,
            "report_generated_at": datetime.now(),
            "overall_status": quality_result["overall_status"],
            "total_checks": quality_result["total_checks"],
            "passed_checks": quality_result["passed_checks"],
            "failed_checks": quality_result["failed_checks"],
        }

        summary_df = pd.DataFrame([summary])

        summary_file = os.path.join(
            self.report_directory,
            f"quality_summary_{context.batch_id}.csv"
        )

        summary_df.to_csv(
            summary_file,
            index=False
        )

        # ---------------------------------------------------------
        # Store report information in context
        # ---------------------------------------------------------

        context.final_report = {
            "batch_id": context.batch_id,
            "overall_status": quality_result["overall_status"],
            "total_checks": quality_result["total_checks"],
            "passed_checks": quality_result["passed_checks"],
            "failed_checks": quality_result["failed_checks"],
            "detail_report": detail_file,
            "summary_report": summary_file,
        }

        self.logger.info(
            f"Detailed quality report generated: {detail_file}"
        )

        self.logger.info(
            f"Quality summary generated: {summary_file}"
        )

        return context.final_report