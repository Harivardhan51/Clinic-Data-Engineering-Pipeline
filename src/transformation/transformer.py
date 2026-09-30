from decimal import Decimal
from datetime import datetime, date, time, timedelta

import pandas as pd
from psycopg2.extras import execute_values


class Transformer:
    """
    Transform raw healthcare data into normalized core tables.

    Raw tables:
        raw.patients_file
        raw.providers_file
        raw.appointments_file
        raw.payments_file

    Core tables:
        core.locations
        core.patients
        core.providers
        core.procedure_types
        core.appointments
        core.insurance_payers
        core.claims
        core.payments
    """

    def __init__(self, config, logger, database_manager):

        self.config = config
        self.logger = logger
        self.db = database_manager

        self.tables = self.config.get_tables()

    # =========================================================
    # MAIN TRANSFORMATION
    # =========================================================

    def run(self, context):
        """
        Run the complete raw-to-core transformation.
        """

        self.logger.info(
            f"Starting transformation for batch "
            f"{context.batch_id}..."
        )

        try:

            # -------------------------------------------------
            # STEP 1: READ RAW DATA
            # -------------------------------------------------

            patients = self._read_table(
                self.tables["raw_patients"],
                context.batch_id
            )

            providers = self._read_table(
                self.tables["raw_providers"],
                context.batch_id
            )

            appointments = self._read_table(
                self.tables["raw_appointments"],
                context.batch_id
            )

            payments = self._read_table(
                self.tables["raw_payments"],
                context.batch_id
            )

            # -------------------------------------------------
            # RAW COUNTS
            # -------------------------------------------------

            self.logger.info(
                f"Raw patients: {len(patients)}"
            )

            self.logger.info(
                f"Raw providers: {len(providers)}"
            )

            self.logger.info(
                f"Raw appointments: {len(appointments)}"
            )

            self.logger.info(
                f"Raw payments: {len(payments)}"
            )

            # -------------------------------------------------
            # SAFETY CHECK
            # -------------------------------------------------

            raw_counts = {
                "patients": len(patients),
                "providers": len(providers),
                "appointments": len(appointments),
                "payments": len(payments),
            }

            empty_tables = [
                name
                for name, count in raw_counts.items()
                if count == 0
            ]

            if empty_tables:

                message = (
                    "Transformation stopped because no data "
                    f"was found for batch {context.batch_id}. "
                    f"Empty raw datasets: {empty_tables}"
                )

                self.logger.error(message)

                raise ValueError(message)

            # -------------------------------------------------
            # STEP 2: CLEAR CORE TABLES
            # -------------------------------------------------

            self._clear_core_tables()

            # -------------------------------------------------
            # STEP 3: LOCATIONS
            # -------------------------------------------------

            self._load_locations(
                providers
            )

            # -------------------------------------------------
            # STEP 4: PATIENTS
            #
            # source patient_id -> core patient_id
            # -------------------------------------------------

            patient_map = self._load_patients(
                patients
            )

            # -------------------------------------------------
            # STEP 5: PROVIDERS
            #
            # source provider_id -> core provider_id
            # -------------------------------------------------

            provider_map = self._load_providers(
                providers
            )

            # -------------------------------------------------
            # STEP 6: PROCEDURES
            # -------------------------------------------------

            self._load_procedure_types(
                appointments
            )

            # -------------------------------------------------
            # STEP 7: INSURANCE PAYERS
            # -------------------------------------------------

            self._load_insurance_payers(
                patients
            )

            # -------------------------------------------------
            # STEP 8: APPOINTMENTS
            #
            # source appointment_id -> core appointment_id
            # -------------------------------------------------

            appointment_map = self._load_appointments(
                appointments,
                patient_map,
                provider_map
            )

            # -------------------------------------------------
            # STEP 9: CLAIMS
            # -------------------------------------------------

            claim_map = self._load_claims(
                payments,
                appointment_map,
                patient_map
            )

            # -------------------------------------------------
            # STEP 10: PAYMENTS
            # -------------------------------------------------

            self._load_payments(
                payments,
                appointment_map,
                claim_map,
                patient_map
            )

            # -------------------------------------------------
            # UPDATE PIPELINE CONTEXT
            # -------------------------------------------------

            context.transformed_tables = [
                self.tables["core_locations"],
                self.tables["core_patients"],
                self.tables["core_providers"],
                self.tables["core_procedure_types"],
                self.tables["core_appointments"],
                self.tables["core_insurance_payers"],
                self.tables["core_claims"],
                self.tables["core_payments"],
            ]

            self.logger.info(
                "Transformation and core loading completed "
                "successfully."
            )

            return context.transformed_tables

        except Exception as error:

            self.logger.error(
                f"Transformation failed: {error}"
            )

            raise

    # =========================================================
    # READ RAW TABLE
    # =========================================================

    def _read_table(
        self,
        table_name,
        batch_id
    ):
        """
        Read a raw table for a specific batch.
        """

        query = f"""
            SELECT *
            FROM {table_name}
            WHERE batch_id = %s
        """

        rows = self.db.fetch_all(
            query,
            (batch_id,)
        )

        schema_name, table_only = (
            table_name.split(".")
        )

        connection = self.db.connect()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (
                    schema_name,
                    table_only
                )
            )

            columns = [
                row[0]
                for row in cursor.fetchall()
            ]

        return pd.DataFrame(
            rows,
            columns=columns
        )

    # =========================================================
    # CLEAR CORE TABLES
    # =========================================================

    def _clear_core_tables(self):
        """
        Clear core tables in reverse dependency order.
        """

        self.logger.info(
            "Clearing existing core tables..."
        )

        connection = self.db.connect()

        tables = [
            self.tables["core_payments"],
            self.tables["core_claims"],
            self.tables["core_appointments"],
            self.tables["core_providers"],
            self.tables["core_procedure_types"],
            self.tables["core_insurance_payers"],
            self.tables["core_patients"],
            self.tables["core_locations"],
        ]

        try:

            with connection.cursor() as cursor:

                for table in tables:

                    cursor.execute(
                        f"""
                        TRUNCATE TABLE {table}
                        RESTART IDENTITY CASCADE
                        """
                    )

            connection.commit()

            self.logger.info(
                "Core tables cleared."
            )

        except Exception:

            connection.rollback()

            raise

    # =========================================================
    # LOCATIONS
    # =========================================================

    def _load_locations(
        self,
        providers
    ):
        """
        Load unique provider locations.
        """

        self.logger.info(
            "Loading core.locations..."
        )

        columns = [
            "location_code",
            "hospital_name",
            "city",
            "state",
            "zip_code",
            "phone",
        ]

        locations = (
            providers[columns]
            .drop_duplicates(
                subset=["location_code"]
            )
        )

        records = []

        for _, row in locations.iterrows():

            records.append(
                (
                    self._clean(
                        row["location_code"]
                    ),
                    self._clean(
                        row["hospital_name"]
                    ),
                    self._clean(
                        row["city"]
                    ),
                    self._clean(
                        row["state"]
                    ),
                    self._clean(
                        row["zip_code"]
                    ),
                    self._clean(
                        row["phone"]
                    ),
                    True,
                )
            )

        query = """
            INSERT INTO core.locations
            (
                location_code,
                location_name,
                address_city,
                address_state,
                zip_code,
                phone,
                is_active
            )
            VALUES %s
        """

        self._execute_values(
            query,
            records
        )

        self.logger.info(
            f"core.locations loaded: {len(records)}"
        )

    # =========================================================
    # PATIENTS
    # =========================================================

    def _load_patients(
        self,
        patients
    ):
        """
        Load patients.

        Returns:

            source patient_id
                ->
            generated core patient_id
        """

        self.logger.info(
            "Loading core.patients..."
        )

        records = []

        source_patient_ids = []

        for _, row in patients.iterrows():

            source_patient_id = self._clean(
                row["patient_id"]
            )

            patient_number = self._clean(
                row["patient_number"]
            )

            if not source_patient_id:

                raise ValueError(
                    "Patient source ID is empty."
                )

            if not patient_number:

                raise ValueError(
                    f"Patient number is empty "
                    f"for {source_patient_id}"
                )

            records.append(
                (
                    patient_number,

                    self._clean(
                        row["first_name"]
                    ),

                    self._clean(
                        row["last_name"]
                    ),

                    self._date(
                        row["date_of_birth"]
                    ),

                    self._clean(
                        row["gender"]
                    ),

                    self._clean(
                        row["zip_code"]
                    ),

                    self._date(
                        row["registration_date"]
                    ),

                    self._clean(
                        row["patient_status"]
                    ),

                    self._clean(
                        row[
                            "primary_insurance_code"
                        ]
                    ),
                )
            )

            source_patient_ids.append(
                source_patient_id
            )

        query = """
            INSERT INTO core.patients
            (
                patient_number,
                first_name,
                last_name,
                date_of_birth,
                gender,
                zip_code,
                registration_date,
                patient_status,
                primary_insurance_code
            )
            VALUES %s
            RETURNING patient_id
        """

        generated_ids = (
            self._execute_values_returning(
                query,
                records
            )
        )

        if len(generated_ids) != len(
            source_patient_ids
        ):

            raise ValueError(
                "Patient mapping failed."
            )

        patient_map = dict(
            zip(
                source_patient_ids,
                generated_ids
            )
        )

        self.logger.info(
            f"core.patients loaded: "
            f"{len(records)}"
        )

        return patient_map

    # =========================================================
    # PROVIDERS
    # =========================================================

    def _load_providers(
        self,
        providers
    ):
        """
        Load providers.

        Returns:

            source provider_id
                ->
            generated core provider_id
        """

        self.logger.info(
            "Loading core.providers..."
        )

        connection = self.db.connect()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    location_code,
                    location_id
                FROM core.locations
                """
            )

            location_map = {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        records = []

        source_provider_ids = []

        for _, row in providers.iterrows():

            source_provider_id = self._clean(
                row["provider_id"]
            )

            provider_code = self._clean(
                row["provider_code"]
            )

            location_code = self._clean(
                row["location_code"]
            )

            if not source_provider_id:

                raise ValueError(
                    "Provider source ID is empty."
                )

            location_id = location_map.get(
                location_code
            )

            if location_id is None:

                raise ValueError(
                    f"Location not found for provider "
                    f"{provider_code}: "
                    f"{location_code}"
                )

            records.append(
                (
                    provider_code,

                    self._clean(
                        row["first_name"]
                    ),

                    self._clean(
                        row["last_name"]
                    ),

                    self._clean(
                        row["specialization"]
                    ),

                    location_id,

                    self._date(
                        row["hire_date"]
                    ),

                    self._integer(
                        row["years_of_experience"]
                    ),

                    self._clean(
                        row["provider_status"]
                    ),
                )
            )

            source_provider_ids.append(
                source_provider_id
            )

        query = """
            INSERT INTO core.providers
            (
                provider_code,
                first_name,
                last_name,
                specialty,
                primary_location_id,
                hire_date,
                years_of_experience,
                provider_status
            )
            VALUES %s
            RETURNING provider_id
        """

        generated_ids = (
            self._execute_values_returning(
                query,
                records
            )
        )

        if len(generated_ids) != len(
            source_provider_ids
        ):

            raise ValueError(
                "Provider mapping failed."
            )

        provider_map = dict(
            zip(
                source_provider_ids,
                generated_ids
            )
        )

        self.logger.info(
            f"core.providers loaded: "
            f"{len(records)}"
        )

        return provider_map

    # =========================================================
    # PROCEDURE TYPES
    # =========================================================

    def _load_procedure_types(
        self,
        appointments
    ):
        """
        Load unique procedure types.
        """

        self.logger.info(
            "Loading core.procedure_types..."
        )

        columns = [
            "procedure_code",
            "procedure_name",
            "procedure_category",
            "standard_duration_minutes",
            "standard_charge",
        ]

        procedures = (
            appointments[columns]
            .drop_duplicates(
                subset=["procedure_code"]
            )
        )

        records = []

        for _, row in procedures.iterrows():

            procedure_code = self._clean(
                row["procedure_code"]
            )

            if not procedure_code:

                raise ValueError(
                    "Procedure code is empty."
                )

            records.append(
                (
                    procedure_code,

                    self._clean(
                        row["procedure_name"]
                    ),

                    self._clean(
                        row["procedure_category"]
                    ),

                    self._integer(
                        row[
                            "standard_duration_minutes"
                        ]
                    ),

                    self._decimal(
                        row["standard_charge"]
                    ),

                    True,
                )
            )

        query = """
            INSERT INTO core.procedure_types
            (
                procedure_code,
                procedure_name,
                procedure_category,
                standard_duration_minutes,
                standard_charge,
                is_active
            )
            VALUES %s
        """

        self._execute_values(
            query,
            records
        )

        self.logger.info(
            f"core.procedure_types loaded: "
            f"{len(records)}"
        )

    # =========================================================
    # INSURANCE PAYERS
    # =========================================================

    def _load_insurance_payers(
        self,
        patients
    ):
        """
        Load insurance payer master data.
        """

        self.logger.info(
            "Loading core.insurance_payers..."
        )

        payer_names = {
            "HCP": "HealthCare Plus",
            "MED": "Medicare",
            "STAR": "Star Health",
            "CARE": "Care Health",
            "APOLLO": "Apollo Health",
            "SELF": "Self Pay",
        }

        payer_codes = (
            patients[
                "primary_insurance_code"
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

        records = []

        for code in payer_codes:

            code = code.strip()

            if not code:
                continue

            payer_name = payer_names.get(
                code,
                code
            )

            payer_type = (
                "Self Pay"
                if code == "SELF"
                else "Insurance"
            )

            records.append(
                (
                    code,
                    payer_name,
                    payer_type,
                    True,
                )
            )

        query = """
            INSERT INTO core.insurance_payers
            (
                payer_code,
                payer_name,
                payer_type,
                is_active
            )
            VALUES %s
        """

        self._execute_values(
            query,
            records
        )

        self.logger.info(
            f"core.insurance_payers loaded: "
            f"{len(records)}"
        )

    # =========================================================
    # APPOINTMENTS
    # =========================================================

    def _load_appointments(
        self,
        appointments,
        patient_map,
        provider_map
    ):
        """
        Load appointments.

        IMPORTANT:
        core.appointments does NOT contain:
            reason
            diagnosis
            notes

        Therefore these source fields are intentionally
        not inserted.

        Returns:

            source appointment_id
                ->
            generated core appointment_id
        """

        self.logger.info(
            "Loading core.appointments..."
        )

        connection = self.db.connect()

        # -----------------------------------------------------
        # LOCATION MAP
        # -----------------------------------------------------

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    location_code,
                    location_id
                FROM core.locations
                """
            )

            location_map = {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        # -----------------------------------------------------
        # PROCEDURE MAP
        # -----------------------------------------------------

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    procedure_code,
                    procedure_type_id
                FROM core.procedure_types
                """
            )

            procedure_map = {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        records = []

        source_appointment_ids = []

        for _, row in appointments.iterrows():

            source_appointment_id = self._clean(
                row["appointment_id"]
            )

            source_patient_id = self._clean(
                row["patient_id"]
            )

            source_provider_id = self._clean(
                row["provider_id"]
            )

            location_code = self._clean(
                row["location_code"]
            )

            procedure_code = self._clean(
                row["procedure_code"]
            )

            # -------------------------------------------------
            # SOURCE ID VALIDATION
            # -------------------------------------------------

            if not source_appointment_id:

                raise ValueError(
                    "Appointment source ID is empty."
                )

            # -------------------------------------------------
            # SOURCE -> CORE MAPPING
            # -------------------------------------------------

            patient_id = patient_map.get(
                source_patient_id
            )

            provider_id = provider_map.get(
                source_provider_id
            )

            location_id = location_map.get(
                location_code
            )

            procedure_type_id = procedure_map.get(
                procedure_code
            )

            # -------------------------------------------------
            # RELATIONSHIP VALIDATION
            # -------------------------------------------------

            if patient_id is None:

                raise ValueError(
                    f"Patient not found: "
                    f"{source_patient_id}"
                )

            if provider_id is None:

                raise ValueError(
                    f"Provider not found: "
                    f"{source_provider_id}"
                )

            if location_id is None:

                raise ValueError(
                    f"Location not found: "
                    f"{location_code}"
                )

            if procedure_type_id is None:

                raise ValueError(
                    f"Procedure not found: "
                    f"{procedure_code}"
                )

            # -------------------------------------------------
            # SCHEDULED START
            # -------------------------------------------------

            scheduled_start = (
                self._combine_datetime(
                    row["appointment_date"],
                    row["appointment_time"]
                )
            )

            if scheduled_start is None:

                raise ValueError(
                    f"Invalid appointment date/time "
                    f"for {source_appointment_id}"
                )

            # -------------------------------------------------
            # DURATION
            # -------------------------------------------------

            duration = self._integer(
                row[
                    "standard_duration_minutes"
                ]
            )

            # -------------------------------------------------
            # SCHEDULED END
            # -------------------------------------------------

            scheduled_end = None

            if duration is not None:

                scheduled_end = (
                    scheduled_start
                    + timedelta(
                        minutes=duration
                    )
                )

            # -------------------------------------------------
            # BUILD RECORD
            #
            # EXACTLY MATCHES:
            #
            # core.appointments
            #
            # appointment_number
            # patient_id
            # provider_id
            # location_id
            # procedure_type_id
            # scheduled_start
            # scheduled_end
            # appointment_status
            # check_in_time
            # completed_time
            # cancelled_at
            # cancellation_reason
            # -------------------------------------------------

            records.append(
                (
                    self._clean(
                        row["appointment_number"]
                    ),

                    patient_id,

                    provider_id,

                    location_id,

                    procedure_type_id,

                    scheduled_start,

                    scheduled_end,

                    self._clean(
                        row["appointment_status"]
                    ),

                    self._datetime(
                        row["check_in_time"]
                    ),

                    self._datetime(
                        row["completed_time"]
                    ),

                    self._datetime(
                        row["cancelled_at"]
                    ),

                    self._clean(
                        row["cancellation_reason"]
                    ),
                )
            )

            source_appointment_ids.append(
                source_appointment_id
            )

        # -----------------------------------------------------
        # INSERT
        # -----------------------------------------------------

        query = """
            INSERT INTO core.appointments
            (
                appointment_number,
                patient_id,
                provider_id,
                location_id,
                procedure_type_id,
                scheduled_start,
                scheduled_end,
                appointment_status,
                check_in_time,
                completed_time,
                cancelled_at,
                cancellation_reason
            )
            VALUES %s
            RETURNING appointment_id
        """

        generated_ids = (
            self._execute_values_returning(
                query,
                records
            )
        )

        if len(generated_ids) != len(
            source_appointment_ids
        ):

            raise ValueError(
                "Appointment mapping failed."
            )

        appointment_map = dict(
            zip(
                source_appointment_ids,
                generated_ids
            )
        )

        self.logger.info(
            f"core.appointments loaded: "
            f"{len(records)}"
        )

        return appointment_map

    # =========================================================
    # CLAIMS
    # =========================================================

    def _load_claims(
        self,
        payments,
        appointment_map,
        patient_map
    ):
        """
        Load claims.

        Source:
            payments.csv

        Relationships:
            source patient_id
                ->
            core patient_id

            source appointment_id
                ->
            core appointment_id
        """

        self.logger.info(
            "Loading core.claims..."
        )

        connection = self.db.connect()

        # -----------------------------------------------------
        # PAYER MAP
        # -----------------------------------------------------

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    payer_code,
                    payer_id
                FROM core.insurance_payers
                """
            )

            payer_map = {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        # -----------------------------------------------------
        # CORE PATIENT -> INSURANCE MAP
        # -----------------------------------------------------

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    patient_id,
                    primary_insurance_code
                FROM core.patients
                """
            )

            patient_insurance_map = {
                row[0]: row[1]
                for row in cursor.fetchall()
            }

        records = []

        source_claim_numbers = []

        seen_claims = set()

        # -----------------------------------------------------
        # PROCESS CLAIMS
        # -----------------------------------------------------

        for _, row in payments.iterrows():

            claim_number = self._clean(
                row["claim_number"]
            )

            # -------------------------------------------------
            # Payment without claim
            # -------------------------------------------------

            if not claim_number:
                continue

            # -------------------------------------------------
            # Avoid duplicate claim records
            # -------------------------------------------------

            if claim_number in seen_claims:
                continue

            seen_claims.add(
                claim_number
            )

            source_patient_id = self._clean(
                row["patient_id"]
            )

            source_appointment_id = self._clean(
                row["appointment_id"]
            )

            # -------------------------------------------------
            # MAP PATIENT
            # -------------------------------------------------

            patient_id = patient_map.get(
                source_patient_id
            )

            if patient_id is None:

                raise ValueError(
                    f"Patient not found for claim "
                    f"{claim_number}: "
                    f"{source_patient_id}"
                )

            # -------------------------------------------------
            # MAP APPOINTMENT
            # -------------------------------------------------

            appointment_id = (
                appointment_map.get(
                    source_appointment_id
                )
            )

            if appointment_id is None:

                raise ValueError(
                    f"Appointment not found for claim "
                    f"{claim_number}: "
                    f"{source_appointment_id}"
                )

            # -------------------------------------------------
            # GET PAYER CODE
            # -------------------------------------------------

            payer_code = self._clean(
                patient_insurance_map.get(
                    patient_id
                )
            )

            if payer_code is None:

                raise ValueError(
                    f"Insurance payer not found for "
                    f"patient {source_patient_id}"
                )

            # -------------------------------------------------
            # MAP PAYER
            # -------------------------------------------------

            payer_id = payer_map.get(
                payer_code
            )

            if payer_id is None:

                raise ValueError(
                    f"Payer not found: "
                    f"{payer_code}"
                )

            # -------------------------------------------------
            # AMOUNTS
            # -------------------------------------------------

            billed_amount = self._decimal(
                row["amount"]
            )

            allowed_amount = self._decimal(
                row["allowed_amount"]
            )

            insurance_amount = self._decimal(
                row["insurance_amount"]
            )

            patient_amount = self._decimal(
                row["patient_amount"]
            )

            # -------------------------------------------------
            # NULL PROTECTION
            # -------------------------------------------------

            if billed_amount is None:

                billed_amount = Decimal("0")

            if allowed_amount is None:

                allowed_amount = billed_amount

            if insurance_amount is None:

                insurance_amount = Decimal("0")

            if patient_amount is None:

                patient_amount = (
                    allowed_amount
                    - insurance_amount
                )

            # -------------------------------------------------
            # FINANCIAL SAFETY
            # -------------------------------------------------

            if allowed_amount < Decimal("0"):

                allowed_amount = Decimal("0")

            if billed_amount < Decimal("0"):

                billed_amount = Decimal("0")

            if insurance_amount < Decimal("0"):

                insurance_amount = Decimal("0")

            if patient_amount < Decimal("0"):

                patient_amount = Decimal("0")

            if allowed_amount > billed_amount:

                allowed_amount = billed_amount

            if insurance_amount > allowed_amount:

                insurance_amount = allowed_amount

            # -------------------------------------------------
            # BUILD CLAIM
            # -------------------------------------------------

            records.append(
                (
                    claim_number,

                    appointment_id,

                    patient_id,

                    payer_id,

                    billed_amount,

                    allowed_amount,

                    insurance_amount,

                    patient_amount,

                    self._clean(
                        row["claim_status"]
                    ),

                    self._datetime(
                        row["submitted_at"]
                    ),

                    self._datetime(
                        row["processed_at"]
                    ),
                )
            )

            source_claim_numbers.append(
                claim_number
            )

        # -----------------------------------------------------
        # INSERT CLAIMS
        # -----------------------------------------------------

        query = """
            INSERT INTO core.claims
            (
                claim_number,
                appointment_id,
                patient_id,
                payer_id,
                billed_amount,
                allowed_amount,
                insurance_paid_amount,
                patient_responsibility,
                claim_status,
                submitted_at,
                processed_at
            )
            VALUES %s
            RETURNING claim_id
        """

        generated_ids = (
            self._execute_values_returning(
                query,
                records
            )
        )

        if len(generated_ids) != len(
            source_claim_numbers
        ):

            raise ValueError(
                "Claim mapping failed."
            )

        claim_map = dict(
            zip(
                source_claim_numbers,
                generated_ids
            )
        )

        self.logger.info(
            f"core.claims loaded: "
            f"{len(records)}"
        )

        return claim_map

    # =========================================================
    # PAYMENTS
    # =========================================================

    def _load_payments(
        self,
        payments,
        appointment_map,
        claim_map,
        patient_map
    ):
        """
        Load payments.

        Source IDs are translated to generated core IDs.
        """

        self.logger.info(
            "Loading core.payments..."
        )

        records = []

        for _, row in payments.iterrows():

            payment_number = self._clean(
                row["payment_number"]
            )

            source_patient_id = self._clean(
                row["patient_id"]
            )

            source_appointment_id = self._clean(
                row["appointment_id"]
            )

            claim_number = self._clean(
                row["claim_number"]
            )

            # -------------------------------------------------
            # MAP PATIENT
            # -------------------------------------------------

            patient_id = patient_map.get(
                source_patient_id
            )

            if patient_id is None:

                raise ValueError(
                    f"Patient not found for payment "
                    f"{payment_number}: "
                    f"{source_patient_id}"
                )

            # -------------------------------------------------
            # MAP APPOINTMENT
            # -------------------------------------------------

            appointment_id = (
                appointment_map.get(
                    source_appointment_id
                )
            )

            if appointment_id is None:

                raise ValueError(
                    f"Appointment not found for payment "
                    f"{payment_number}: "
                    f"{source_appointment_id}"
                )

            # -------------------------------------------------
            # MAP CLAIM
            # -------------------------------------------------

            claim_id = None

            if claim_number:

                claim_id = claim_map.get(
                    claim_number
                )

                if claim_id is None:

                    raise ValueError(
                        f"Claim not found for payment "
                        f"{payment_number}: "
                        f"{claim_number}"
                    )

            # -------------------------------------------------
            # PAYMENT AMOUNT
            # -------------------------------------------------

            payment_amount = self._decimal(
                row["patient_amount"]
            )

            if payment_amount is None:

                payment_amount = Decimal("0")

            if payment_amount < Decimal("0"):

                payment_amount = Decimal("0")

            # -------------------------------------------------
            # PAYMENT TYPE
            # -------------------------------------------------

            payment_type = "Patient Payment"

            # -------------------------------------------------
            # BUILD RECORD
            # -------------------------------------------------

            records.append(
                (
                    payment_number,

                    patient_id,

                    appointment_id,

                    claim_id,

                    payment_type,

                    payment_amount,

                    self._date(
                        row["payment_date"]
                    ),

                    self._clean(
                        row["payment_status"]
                    ),
                )
            )

        # -----------------------------------------------------
        # INSERT PAYMENTS
        # -----------------------------------------------------

        query = """
            INSERT INTO core.payments
            (
                payment_number,
                patient_id,
                appointment_id,
                claim_id,
                payment_type,
                payment_amount,
                payment_date,
                payment_status
            )
            VALUES %s
        """

        self._execute_values(
            query,
            records
        )

        self.logger.info(
            f"core.payments loaded: "
            f"{len(records)}"
        )

    # =========================================================
    # BULK INSERT
    # =========================================================

    def _execute_values(
        self,
        query,
        records
    ):
        """
        Execute a bulk INSERT.
        """

        if not records:
            return

        connection = self.db.connect()

        try:

            with connection.cursor() as cursor:

                execute_values(
                    cursor,
                    query,
                    records
                )

            connection.commit()

        except Exception:

            connection.rollback()

            raise

    # =========================================================
    # BULK INSERT WITH RETURNING
    # =========================================================

    def _execute_values_returning(
        self,
        query,
        records
    ):
        """
        Execute bulk INSERT and return generated IDs.
        """

        if not records:
            return []

        connection = self.db.connect()

        try:

            with connection.cursor() as cursor:

                returned_rows = execute_values(
                    cursor,
                    query,
                    records,
                    fetch=True
                )

            connection.commit()

            return [
                row[0]
                for row in returned_rows
            ]

        except Exception:

            connection.rollback()

            raise

    # =========================================================
    # CLEAN STRING
    # =========================================================

    @staticmethod
    def _clean(value):
        """
        Convert null/NaN/empty values to None.
        """

        if value is None:
            return None

        try:

            if pd.isna(value):
                return None

        except (TypeError, ValueError):

            pass

        value = str(value).strip()

        if value == "":
            return None

        return value

    # =========================================================
    # INTEGER
    # =========================================================

    @staticmethod
    def _integer(value):
        """
        Convert value to integer.
        """

        if value is None:
            return None

        try:

            if pd.isna(value):
                return None

        except (TypeError, ValueError):

            pass

        try:

            return int(
                float(value)
            )

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                f"Invalid integer value: {value}"
            )

    # =========================================================
    # DECIMAL
    # =========================================================

    @staticmethod
    def _decimal(value):
        """
        Convert value to Decimal.
        """

        if value is None:
            return None

        try:

            if pd.isna(value):
                return None

        except (TypeError, ValueError):

            pass

        try:

            return Decimal(
                str(value).strip()
            )

        except Exception:

            raise ValueError(
                f"Invalid decimal value: {value}"
            )

    # =========================================================
    # DATE
    # =========================================================

    @staticmethod
    def _date(value):
        """
        Convert value to Python date.
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime
        ):

            return value.date()

        if isinstance(
            value,
            date
        ):

            return value

        try:

            if pd.isna(value):
                return None

        except (TypeError, ValueError):

            pass

        parsed = pd.to_datetime(
            value,
            errors="coerce"
        )

        if pd.isna(parsed):
            return None

        if isinstance(
            parsed,
            pd.Timestamp
        ):

            return parsed.date()

        if isinstance(
            parsed,
            datetime
        ):

            return parsed.date()

        return None

    # =========================================================
    # DATETIME
    # =========================================================

    @staticmethod
    def _datetime(value):
        """
        Convert value to Python datetime.

        Supports:
            pandas Timestamp
            Python datetime
            Python date
            strings
            null values
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime
        ):

            return value

        if isinstance(
            value,
            date
        ):

            return datetime.combine(
                value,
                time.min
            )

        try:

            if pd.isna(value):
                return None

        except (TypeError, ValueError):

            pass

        parsed = pd.to_datetime(
            value,
            errors="coerce"
        )

        if pd.isna(parsed):
            return None

        if isinstance(
            parsed,
            pd.Timestamp
        ):

            return parsed.to_pydatetime()

        if isinstance(
            parsed,
            datetime
        ):

            return parsed

        return None

    # =========================================================
    # COMBINE DATE + TIME
    # =========================================================

    @staticmethod
    def _combine_datetime(
        date_value,
        time_value
    ):
        """
        Combine appointment date and appointment time.

        Always returns a normal Python datetime.
        """

        if date_value is None:
            return None

        if time_value is None:
            return None

        # -----------------------------------------------------
        # DATE NULL CHECK
        # -----------------------------------------------------

        try:

            if pd.isna(date_value):
                return None

        except (TypeError, ValueError):

            pass

        # -----------------------------------------------------
        # TIME NULL CHECK
        # -----------------------------------------------------

        try:

            if pd.isna(time_value):
                return None

        except (TypeError, ValueError):

            pass

        # -----------------------------------------------------
        # DATE
        # -----------------------------------------------------

        if isinstance(
            date_value,
            datetime
        ):

            base_date = date_value.date()

        elif isinstance(
            date_value,
            date
        ):

            base_date = date_value

        else:

            parsed_date = pd.to_datetime(
                date_value,
                errors="coerce"
            )

            if pd.isna(parsed_date):
                return None

            if isinstance(
                parsed_date,
                pd.Timestamp
            ):

                base_date = parsed_date.date()

            else:

                base_date = parsed_date.date()

        # -----------------------------------------------------
        # TIME
        # -----------------------------------------------------

        if isinstance(
            time_value,
            time
        ):

            appointment_time = time_value

        elif isinstance(
            time_value,
            datetime
        ):

            appointment_time = time_value.time()

        else:

            time_string = str(
                time_value
            ).strip()

            # HH:MM:SS
            parsed_time = pd.to_datetime(
                time_string,
                format="%H:%M:%S",
                errors="coerce"
            )

            # HH:MM
            if pd.isna(parsed_time):

                parsed_time = pd.to_datetime(
                    time_string,
                    format="%H:%M",
                    errors="coerce"
                )

            # General fallback
            if pd.isna(parsed_time):

                parsed_time = pd.to_datetime(
                    time_string,
                    errors="coerce"
                )

            if pd.isna(parsed_time):
                return None

            if isinstance(
                parsed_time,
                pd.Timestamp
            ):

                appointment_time = (
                    parsed_time.time()
                )

            else:

                appointment_time = (
                    parsed_time.time()
                )

        # -----------------------------------------------------
        # RETURN PYTHON DATETIME
        # -----------------------------------------------------

        return datetime.combine(
            base_date,
            appointment_time
        )