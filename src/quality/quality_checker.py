from datetime import datetime


class QualityChecker:
    """
    Performs post-transformation data quality checks
    against the PostgreSQL core tables.
    """

    def __init__(self, config, logger, db):
        self.config = config
        self.logger = logger
        self.db = db

    def run(self, context):
        self.logger.info(
            f"Starting quality checks for batch {context.batch_id}..."
        )

        results = []

        # ---------------------------------------------------------
        # 1. Row count checks
        # ---------------------------------------------------------
        results.extend(self._check_row_counts())

        # ---------------------------------------------------------
        # 2. Primary key checks
        # ---------------------------------------------------------
        results.extend(self._check_primary_keys())

        # ---------------------------------------------------------
        # 3. Foreign key / relationship checks
        # ---------------------------------------------------------
        results.extend(self._check_relationships())

        # ---------------------------------------------------------
        # 4. Critical NULL checks
        # ---------------------------------------------------------
        results.extend(self._check_nulls())

        # ---------------------------------------------------------
        # 5. Financial consistency checks
        # ---------------------------------------------------------
        results.extend(self._check_financials())

        # ---------------------------------------------------------
        # Final status
        # ---------------------------------------------------------
        failed = [r for r in results if r["status"] == "FAIL"]

        overall_status = "FAIL" if failed else "PASS"

        quality_result = {
            "batch_id": context.batch_id,
            "checked_at": datetime.now(),
            "overall_status": overall_status,
            "total_checks": len(results),
            "passed_checks": len(
                [r for r in results if r["status"] == "PASS"]
            ),
            "failed_checks": len(failed),
            "checks": results,
        }

        context.quality_result = quality_result

        if overall_status == "PASS":
            self.logger.info(
                f"Quality checks completed successfully. "
                f"{len(results)} checks passed."
            )
        else:
            self.logger.error(
                f"Quality checks completed with "
                f"{len(failed)} failure(s)."
            )

        return quality_result

    # =============================================================
    # ROW COUNT CHECKS
    # =============================================================

    def _check_row_counts(self):
        checks = []

        expected_counts = {
            "core.locations": 5,
            "core.patients": 1000,
            "core.providers": 100,
            "core.procedure_types": 10,
            "core.appointments": 5000,
            "core.insurance_payers": 6,
            "core.claims": 5000,
            "core.payments": 5000,
        }

        for table, expected in expected_counts.items():

            actual = self.db.table_count(table)

            status = "PASS" if actual == expected else "FAIL"

            checks.append({
                "check_name": f"Row count - {table}",
                "category": "Row Count",
                "status": status,
                "expected": expected,
                "actual": actual,
                "message": (
                    "Row count matches expected value."
                    if status == "PASS"
                    else f"Expected {expected}, found {actual}."
                ),
            })

        return checks

    # =============================================================
    # PRIMARY KEY CHECKS
    # =============================================================

    def _check_primary_keys(self):
        checks = []

        primary_keys = {
            "core.locations": "location_id",
            "core.patients": "patient_id",
            "core.providers": "provider_id",
            "core.procedure_types": "procedure_type_id",
            "core.appointments": "appointment_id",
            "core.insurance_payers": "payer_id",
            "core.claims": "claim_id",
            "core.payments": "payment_id",
        }

        for table, column in primary_keys.items():

            sql = f"""
                SELECT COUNT(*) - COUNT(DISTINCT {column})
                FROM {table};
            """

            result = self.db.fetch_one(sql)
            duplicate_count = result[0]

            status = "PASS" if duplicate_count == 0 else "FAIL"

            checks.append({
                "check_name": f"Primary key uniqueness - {table}",
                "category": "Primary Key",
                "status": status,
                "expected": 0,
                "actual": duplicate_count,
                "message": (
                    "No duplicate primary keys found."
                    if status == "PASS"
                    else f"{duplicate_count} duplicate key(s) found."
                ),
            })

        return checks

    # =============================================================
    # RELATIONSHIP CHECKS
    # =============================================================

    def _check_relationships(self):
        checks = []

        relationship_queries = [

            {
                "name": "Appointments → Patients",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.appointments a
                    LEFT JOIN core.patients p
                        ON a.patient_id = p.patient_id
                    WHERE p.patient_id IS NULL;
                """,
            },

            {
                "name": "Appointments → Providers",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.appointments a
                    LEFT JOIN core.providers p
                        ON a.provider_id = p.provider_id
                    WHERE p.provider_id IS NULL;
                """,
            },

            {
                "name": "Appointments → Locations",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.appointments a
                    LEFT JOIN core.locations l
                        ON a.location_id = l.location_id
                    WHERE l.location_id IS NULL;
                """,
            },

            {
                "name": "Appointments → Procedure Types",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.appointments a
                    LEFT JOIN core.procedure_types pt
                        ON a.procedure_type_id = pt.procedure_type_id
                    WHERE pt.procedure_type_id IS NULL;
                """,
            },

            {
                "name": "Claims → Appointments",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.claims c
                    LEFT JOIN core.appointments a
                        ON c.appointment_id = a.appointment_id
                    WHERE a.appointment_id IS NULL;
                """,
            },

            {
                "name": "Claims → Patients",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.claims c
                    LEFT JOIN core.patients p
                        ON c.patient_id = p.patient_id
                    WHERE p.patient_id IS NULL;
                """,
            },

            {
                "name": "Claims → Insurance Payers",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.claims c
                    LEFT JOIN core.insurance_payers ip
                        ON c.payer_id = ip.payer_id
                    WHERE ip.payer_id IS NULL;
                """,
            },

            {
                "name": "Payments → Appointments",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.payments p
                    LEFT JOIN core.appointments a
                        ON p.appointment_id = a.appointment_id
                    WHERE a.appointment_id IS NULL;
                """,
            },

            {
                "name": "Payments → Patients",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.payments p
                    LEFT JOIN core.patients pt
                        ON p.patient_id = pt.patient_id
                    WHERE pt.patient_id IS NULL;
                """,
            },

            {
                "name": "Payments → Claims",
                "sql": """
                    SELECT COUNT(*)
                    FROM core.payments p
                    LEFT JOIN core.claims c
                        ON p.claim_id = c.claim_id
                    WHERE p.claim_id IS NOT NULL
                      AND c.claim_id IS NULL;
                """,
            },
        ]

        for relationship in relationship_queries:

            orphan_count = self.db.fetch_one(
                relationship["sql"]
            )[0]

            status = "PASS" if orphan_count == 0 else "FAIL"

            checks.append({
                "check_name": relationship["name"],
                "category": "Relationship",
                "status": status,
                "expected": 0,
                "actual": orphan_count,
                "message": (
                    "All references are valid."
                    if status == "PASS"
                    else f"{orphan_count} invalid reference(s) found."
                ),
            })

        return checks

    # =============================================================
    # NULL CHECKS
    # =============================================================

    def _check_nulls(self):
        checks = []

        null_checks = {
            "core.locations.location_id": """
                SELECT COUNT(*)
                FROM core.locations
                WHERE location_id IS NULL;
            """,

            "core.patients.patient_id": """
                SELECT COUNT(*)
                FROM core.patients
                WHERE patient_id IS NULL;
            """,

            "core.providers.provider_id": """
                SELECT COUNT(*)
                FROM core.providers
                WHERE provider_id IS NULL;
            """,

            "core.appointments.appointment_id": """
                SELECT COUNT(*)
                FROM core.appointments
                WHERE appointment_id IS NULL;
            """,

            "core.appointments.patient_id": """
                SELECT COUNT(*)
                FROM core.appointments
                WHERE patient_id IS NULL;
            """,

            "core.appointments.provider_id": """
                SELECT COUNT(*)
                FROM core.appointments
                WHERE provider_id IS NULL;
            """,

            "core.claims.claim_id": """
                SELECT COUNT(*)
                FROM core.claims
                WHERE claim_id IS NULL;
            """,

            "core.payments.payment_id": """
                SELECT COUNT(*)
                FROM core.payments
                WHERE payment_id IS NULL;
            """,

            "core.payments.payment_amount": """
                SELECT COUNT(*)
                FROM core.payments
                WHERE payment_amount IS NULL;
            """,
        }

        for field, sql in null_checks.items():

            null_count = self.db.fetch_one(sql)[0]

            status = "PASS" if null_count == 0 else "FAIL"

            checks.append({
                "check_name": f"NULL check - {field}",
                "category": "NULL Check",
                "status": status,
                "expected": 0,
                "actual": null_count,
                "message": (
                    "No NULL values found."
                    if status == "PASS"
                    else f"{null_count} NULL value(s) found."
                ),
            })

        return checks

    # =============================================================
    # FINANCIAL CHECKS
    # =============================================================

    def _check_financials(self):
        checks = []

        # Billed amount cannot be negative
        sql = """
            SELECT COUNT(*)
            FROM core.claims
            WHERE billed_amount < 0;
        """

        negative_billed = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Claims - negative billed amount",
            "category": "Financial",
            "status": "PASS" if negative_billed == 0 else "FAIL",
            "expected": 0,
            "actual": negative_billed,
            "message": (
                "No negative billed amounts."
                if negative_billed == 0
                else f"{negative_billed} negative billed amount(s)."
            ),
        })

        # Allowed amount cannot exceed billed amount
        sql = """
            SELECT COUNT(*)
            FROM core.claims
            WHERE allowed_amount > billed_amount;
        """

        invalid_allowed = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Claims - allowed <= billed",
            "category": "Financial",
            "status": "PASS" if invalid_allowed == 0 else "FAIL",
            "expected": 0,
            "actual": invalid_allowed,
            "message": (
                "Allowed amount is valid."
                if invalid_allowed == 0
                else f"{invalid_allowed} invalid claim(s)."
            ),
        })

        # Insurance payment cannot exceed allowed amount
        sql = """
            SELECT COUNT(*)
            FROM core.claims
            WHERE insurance_paid_amount > allowed_amount;
        """

        invalid_insurance = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Claims - insurance paid <= allowed",
            "category": "Financial",
            "status": "PASS" if invalid_insurance == 0 else "FAIL",
            "expected": 0,
            "actual": invalid_insurance,
            "message": (
                "Insurance payment is valid."
                if invalid_insurance == 0
                else f"{invalid_insurance} invalid claim(s)."
            ),
        })

        # Patient responsibility cannot be negative
        sql = """
            SELECT COUNT(*)
            FROM core.claims
            WHERE patient_responsibility < 0;
        """

        negative_patient = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Claims - patient responsibility >= 0",
            "category": "Financial",
            "status": "PASS" if negative_patient == 0 else "FAIL",
            "expected": 0,
            "actual": negative_patient,
            "message": (
                "Patient responsibility is valid."
                if negative_patient == 0
                else f"{negative_patient} negative value(s)."
            ),
        })

        # Claim amount reconciliation
        sql = """
            SELECT COUNT(*)
            FROM core.claims
            WHERE ABS(
                COALESCE(allowed_amount, 0)
                -
                COALESCE(insurance_paid_amount, 0)
                -
                COALESCE(patient_responsibility, 0)
            ) > 0.01;
        """

        reconciliation_errors = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Claims - financial reconciliation",
            "category": "Financial",
            "status": (
                "PASS"
                if reconciliation_errors == 0
                else "FAIL"
            ),
            "expected": 0,
            "actual": reconciliation_errors,
            "message": (
                "Financial amounts reconcile."
                if reconciliation_errors == 0
                else (
                    f"{reconciliation_errors} claim(s) "
                    "failed reconciliation."
                )
            ),
        })

        # Payments cannot be negative
        sql = """
            SELECT COUNT(*)
            FROM core.payments
            WHERE payment_amount < 0;
        """

        negative_payments = self.db.fetch_one(sql)[0]

        checks.append({
            "check_name": "Payments - negative payment amount",
            "category": "Financial",
            "status": (
                "PASS"
                if negative_payments == 0
                else "FAIL"
            ),
            "expected": 0,
            "actual": negative_payments,
            "message": (
                "No negative payments."
                if negative_payments == 0
                else f"{negative_payments} negative payment(s)."
            ),
        })

        return checks