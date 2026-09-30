import sys
import uuid
from datetime import datetime

from src.config.config_manager import ConfigManager
from src.database.database_manager import DatabaseManager

from src.pipeline.context import PipelineContext
from src.pipeline.logger import PipelineLogger

from src.ingestion.data_generator import DataGenerator
from src.ingestion.raw_loader import RawLoader

from src.quality.validator import Validator
from src.quality.quality_checker import QualityChecker

from src.transformation.transformer import Transformer

from src.reporting.report_generator import ReportGenerator


# =============================================================
# BATCH ID GENERATOR
# =============================================================

def generate_batch_id():
    """
    Generate a unique batch ID for each pipeline execution.
    """

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    unique_id = uuid.uuid4().hex[:6].upper()

    return (
        f"BATCH_{timestamp}_{unique_id}"
    )


# =============================================================
# MAIN PIPELINE
# =============================================================

def main():

    print("=" * 80)
    print("CLINIC DATA ENGINEERING PIPELINE")
    print("=" * 80)

    logger = None
    db = None
    context = None

    try:

        # =====================================================
        # INITIALIZATION
        # =====================================================

        config = ConfigManager()

        logger = PipelineLogger()

        db = DatabaseManager(
            config
        )

        context = PipelineContext()

        context.batch_id = generate_batch_id()

        logger.info(
            f"Pipeline started. Batch ID: {context.batch_id}"
        )

        print(
            f"\nBatch ID: {context.batch_id}"
        )

        # =====================================================
        # STEP 1
        # DATA GENERATION
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 1 - DATA GENERATION")
        print("-" * 80)

        generator = DataGenerator(
            config,
            logger
        )

        generator.run(
            context
        )

        logger.info(
            "STEP 1 completed successfully."
        )

        # =====================================================
        # STEP 2
        # DATA VALIDATION
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 2 - DATA VALIDATION")
        print("-" * 80)

        validator = Validator(
            config,
            logger
        )

        validator.run(
            context
        )

        logger.info(
            "STEP 2 completed successfully."
        )

        # =====================================================
        # STEP 3
        # RAW DATA LOAD
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 3 - RAW DATA LOAD")
        print("-" * 80)

        raw_loader = RawLoader(
            config,
            logger,
            db
        )

        raw_loader.run(
            context
        )

        logger.info(
            "STEP 3 completed successfully."
        )

        # =====================================================
        # STEP 4
        # TRANSFORMATION + CORE LOAD
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 4 - TRANSFORMATION AND CORE LOAD")
        print("-" * 80)

        transformer = Transformer(
            config,
            logger,
            db
        )

        transformer.run(
            context
        )

        logger.info(
            "STEP 4 completed successfully."
        )

        # =====================================================
        # STEP 5
        # QUALITY CHECK
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 5 - QUALITY CHECK")
        print("-" * 80)

        quality_checker = QualityChecker(
            config,
            logger,
            db
        )

        quality_result = quality_checker.run(
            context
        )

        # -----------------------------------------------------
        # Stop pipeline if quality checks fail
        # -----------------------------------------------------

        if quality_result["overall_status"] != "PASS":

            raise RuntimeError(
                "Quality checks failed."
            )

        logger.info(
            "STEP 5 completed successfully."
        )

        # =====================================================
        # STEP 6
        # REPORT GENERATION
        # =====================================================

        print("\n" + "-" * 80)
        print("STEP 6 - REPORT GENERATION")
        print("-" * 80)

        report_generator = ReportGenerator(
            config,
            logger
        )

        report_result = report_generator.run(
            context
        )

        logger.info(
            "STEP 6 completed successfully."
        )

        # =====================================================
        # PIPELINE SUCCESS
        # =====================================================

        context.mark_completed()

        duration = context.get_duration_seconds()

        print("\n" + "=" * 80)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 80)

        print(
            f"\nBatch ID:       {context.batch_id}"
        )

        print(
            f"Status:         {context.status}"
        )

        print(
            f"Duration:       {duration:.2f} seconds"
        )

        print(
            f"Quality Status: "
            f"{quality_result['overall_status']}"
        )

        print(
            f"Quality Checks: "
            f"{quality_result['passed_checks']}/"
            f"{quality_result['total_checks']} passed"
        )

        print(
            "\nDetailed Report:"
        )

        print(
            report_result["detail_report"]
        )

        print(
            "\nSummary Report:"
        )

        print(
            report_result["summary_report"]
        )

        print(
            "\n" + "=" * 80
        )

        return 0

    except Exception as e:

        # =====================================================
        # PIPELINE FAILURE
        # =====================================================

        error_message = str(e)

        if logger:

            logger.exception(
                f"Pipeline failed: {error_message}"
            )

        if context:

            # PipelineContext.mark_failed()
            # does not accept an error argument.
            context.mark_failed()

        print("\n" + "=" * 80)
        print("PIPELINE FAILED")
        print("=" * 80)

        if context:

            print(
                f"\nBatch ID: "
                f"{context.batch_id}"
            )

            print(
                f"Status: "
                f"{context.status}"
            )

            print(
                f"Duration: "
                f"{context.get_duration_seconds():.2f} seconds"
            )

        else:

            print(
                "\nBatch ID: UNKNOWN"
            )

        print(
            f"Error: {error_message}"
        )

        print(
            "\nCheck logs/pipeline.log for details."
        )

        print(
            "=" * 80
        )

        return 1

    finally:

        # =====================================================
        # CLEANUP
        # =====================================================

        if db:

            db.close()

        if logger:

            logger.info(
                "Pipeline resources closed."
            )


# =============================================================
# PROGRAM ENTRY POINT
# =============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )