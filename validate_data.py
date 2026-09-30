import os
from datetime import datetime

import pandas as pd


# =============================================================
# PATH CONFIGURATION
# =============================================================

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

PATIENTS_FILE = os.path.join(
    RAW_DIR,
    "patients.csv"
)

PROVIDERS_FILE = os.path.join(
    RAW_DIR,
    "providers.csv"
)

APPOINTMENTS_FILE = os.path.join(
    RAW_DIR,
    "appointments.csv"
)

PAYMENTS_FILE = os.path.join(
    RAW_DIR,
    "payments.csv"
)

REPORT_FILE = os.path.join(
    PROCESSED_DIR,
    "validation_report.csv"
)


# =============================================================
# RESULT HELPER
# =============================================================

def add_result(
    results,
    dataset,
    check_name,
    status,
    error_count,
    message
):
    results.append({
        "dataset": dataset,
        "check_name": check_name,
        "status": status,
        "error_count": error_count,
        "message": message
    })


# =============================================================
# REQUIRED COLUMN VALIDATION
# =============================================================

def validate_required_columns(
    df,
    dataset,
    required_columns,
    results
):
    actual_columns = set(df.columns)

    missing_columns = [
        column
        for column in required_columns
        if column not in actual_columns
    ]

    if missing_columns:

        add_result(
            results,
            dataset,
            "Required columns",
            "FAIL",
            len(missing_columns),
            f"Missing columns: {', '.join(missing_columns)}"
        )

        return False

    add_result(
        results,
        dataset,
        "Required columns",
        "PASS",
        0,
        "All required columns are present."
    )

    return True


# =============================================================
# NULL PRIMARY KEY VALIDATION
# =============================================================

def validate_null_primary_keys(
    df,
    dataset,
    primary_key,
    results
):
    null_count = int(
        df[primary_key].isna().sum()
    )

    status = (
        "PASS"
        if null_count == 0
        else "FAIL"
    )

    add_result(
        results,
        dataset,
        f"NULL primary key - {primary_key}",
        status,
        null_count,
        (
            "No NULL primary keys found."
            if status == "PASS"
            else f"{null_count} NULL primary key value(s) found."
        )
    )


# =============================================================
# DUPLICATE PRIMARY KEY VALIDATION
# =============================================================

def validate_duplicate_ids(
    df,
    dataset,
    primary_key,
    results
):
    duplicate_count = int(
        df[primary_key].duplicated().sum()
    )

    status = (
        "PASS"
        if duplicate_count == 0
        else "FAIL"
    )

    add_result(
        results,
        dataset,
        f"Duplicate primary key - {primary_key}",
        status,
        duplicate_count,
        (
            "No duplicate primary keys found."
            if status == "PASS"
            else (
                f"{duplicate_count} duplicate "
                "primary key value(s) found."
            )
        )
    )


# =============================================================
# APPOINTMENT STATUS VALIDATION
# =============================================================

def validate_appointment_statuses(
    appointments,
    results
):
    valid_statuses = {
        "Scheduled",
        "Confirmed",
        "Completed",
        "Cancelled",
        "No Show"
    }

    invalid_mask = ~appointments[
        "appointment_status"
    ].isin(valid_statuses)

    invalid_count = int(
        invalid_mask.sum()
    )

    status = (
        "PASS"
        if invalid_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "appointments",
        "Appointment status values",
        status,
        invalid_count,
        (
            "All appointment statuses are valid."
            if status == "PASS"
            else (
                f"{invalid_count} invalid appointment "
                "status value(s) found."
            )
        )
    )


# =============================================================
# NEGATIVE PAYMENT VALIDATION
# =============================================================

def validate_negative_payment_amounts(
    payments,
    results
):
    amount = pd.to_numeric(
        payments["amount"],
        errors="coerce"
    )

    invalid_count = int(
        (amount < 0).sum()
    )

    status = (
        "PASS"
        if invalid_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Negative payment amounts",
        status,
        invalid_count,
        (
            "No negative payment amounts found."
            if status == "PASS"
            else (
                f"{invalid_count} negative payment "
                "amount(s) found."
            )
        )
    )


# =============================================================
# APPOINTMENT → PATIENT VALIDATION
# =============================================================

def validate_patient_references(
    appointments,
    patients,
    results
):
    patient_ids = set(
        patients["patient_id"].dropna()
    )

    invalid_count = int(
        (
            ~appointments["patient_id"].isin(
                patient_ids
            )
        ).sum()
    )

    status = (
        "PASS"
        if invalid_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "appointments",
        "Appointment → Patient references",
        status,
        invalid_count,
        (
            "All appointment patient references are valid."
            if status == "PASS"
            else (
                f"{invalid_count} appointment(s) "
                "reference missing patients."
            )
        )
    )


# =============================================================
# APPOINTMENT → PROVIDER VALIDATION
# =============================================================

def validate_provider_references(
    appointments,
    providers,
    results
):
    provider_ids = set(
        providers["provider_id"].dropna()
    )

    invalid_count = int(
        (
            ~appointments["provider_id"].isin(
                provider_ids
            )
        ).sum()
    )

    status = (
        "PASS"
        if invalid_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "appointments",
        "Appointment → Provider references",
        status,
        invalid_count,
        (
            "All appointment provider references are valid."
            if status == "PASS"
            else (
                f"{invalid_count} appointment(s) "
                "reference missing providers."
            )
        )
    )


# =============================================================
# PAYMENT → APPOINTMENT VALIDATION
# =============================================================

def validate_payment_appointment_references(
    payments,
    appointments,
    results
):
    appointment_ids = set(
        appointments["appointment_id"].dropna()
    )

    invalid_count = int(
        (
            ~payments["appointment_id"].isin(
                appointment_ids
            )
        ).sum()
    )

    status = (
        "PASS"
        if invalid_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Payment → Appointment references",
        status,
        invalid_count,
        (
            "All payment appointment references are valid."
            if status == "PASS"
            else (
                f"{invalid_count} payment(s) "
                "reference missing appointments."
            )
        )
    )


# =============================================================
# DATE VALIDATION
# =============================================================

def validate_dates(
    df,
    dataset,
    date_columns,
    results
):
    for column in date_columns:

        if column not in df.columns:
            continue

        parsed_dates = pd.to_datetime(
            df[column],
            errors="coerce"
        )

        original_non_null = df[column].notna()

        invalid_count = int(
            (
                original_non_null
                & parsed_dates.isna()
            ).sum()
        )

        status = (
            "PASS"
            if invalid_count == 0
            else "FAIL"
        )

        add_result(
            results,
            dataset,
            f"Valid dates - {column}",
            status,
            invalid_count,
            (
                "All populated date values are valid."
                if status == "PASS"
                else (
                    f"{invalid_count} invalid date "
                    "value(s) found."
                )
            )
        )


# =============================================================
# FINANCIAL VALIDATION
# =============================================================

def validate_financial_consistency(
    payments,
    results
):
    amount = pd.to_numeric(
        payments["amount"],
        errors="coerce"
    )

    allowed = pd.to_numeric(
        payments["allowed_amount"],
        errors="coerce"
    )

    insurance = pd.to_numeric(
        payments["insurance_amount"],
        errors="coerce"
    )

    patient = pd.to_numeric(
        payments["patient_amount"],
        errors="coerce"
    )

    # ---------------------------------------------------------
    # Check 1
    # Allowed amount <= billed amount
    # ---------------------------------------------------------

    invalid_allowed = (
        allowed > amount
    )

    invalid_allowed_count = int(
        invalid_allowed.fillna(False).sum()
    )

    status = (
        "PASS"
        if invalid_allowed_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Allowed amount <= billed amount",
        status,
        invalid_allowed_count,
        (
            "Allowed amounts are valid."
            if status == "PASS"
            else (
                f"{invalid_allowed_count} record(s) "
                "have allowed amount greater than "
                "billed amount."
            )
        )
    )

    # ---------------------------------------------------------
    # Check 2
    # Insurance amount <= allowed amount
    # ---------------------------------------------------------

    invalid_insurance = (
        insurance > allowed
    )

    invalid_insurance_count = int(
        invalid_insurance.fillna(False).sum()
    )

    status = (
        "PASS"
        if invalid_insurance_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Insurance amount <= allowed amount",
        status,
        invalid_insurance_count,
        (
            "Insurance amounts are valid."
            if status == "PASS"
            else (
                f"{invalid_insurance_count} record(s) "
                "have insurance amount greater than "
                "allowed amount."
            )
        )
    )

    # ---------------------------------------------------------
    # Check 3
    # Patient amount reconciliation
    #
    # patient_amount =
    # allowed_amount - insurance_amount
    # ---------------------------------------------------------

    expected_patient = (
        allowed - insurance
    )

    reconciliation_mask = (
        (patient - expected_patient).abs() > 0.01
    )

    reconciliation_count = int(
        reconciliation_mask.fillna(False).sum()
    )

    status = (
        "PASS"
        if reconciliation_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Patient amount reconciliation",
        status,
        reconciliation_count,
        (
            "Patient amounts reconcile correctly."
            if status == "PASS"
            else (
                f"{reconciliation_count} record(s) "
                "have inconsistent patient amounts."
            )
        )
    )

    # ---------------------------------------------------------
    # Check 4
    # Self-pay financial consistency
    #
    # SELF:
    #
    # allowed_amount = amount
    # insurance_amount = 0
    # patient_amount = amount
    # ---------------------------------------------------------

    if "insurance_provider" in payments.columns:

        self_pay = (
            payments["insurance_provider"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq("SELF")
        )

    else:

        self_pay = pd.Series(
            False,
            index=payments.index
        )

    # IMPORTANT:
    # Each comparison is wrapped in parentheses.
    # This prevents Pandas/Python operator-precedence
    # errors with the "|" operator.

    self_pay_errors = (
        self_pay
        & (
            ((allowed - amount).abs() > 0.01)
            | (insurance.abs() > 0.01)
            | ((patient - amount).abs() > 0.01)
        )
    )

    self_pay_error_count = int(
        self_pay_errors.fillna(False).sum()
    )

    status = (
        "PASS"
        if self_pay_error_count == 0
        else "FAIL"
    )

    add_result(
        results,
        "payments",
        "Self-pay financial consistency",
        status,
        self_pay_error_count,
        (
            "Self-pay financial values are consistent."
            if status == "PASS"
            else (
                f"{self_pay_error_count} self-pay "
                "record(s) are financially inconsistent."
            )
        )
    )


# =============================================================
# MAIN VALIDATION FUNCTION
# =============================================================

def main():

    print("=" * 70)
    print("CLINIC DATA VALIDATION")
    print("=" * 70)

    os.makedirs(
        PROCESSED_DIR,
        exist_ok=True
    )

    results = []

    # =========================================================
    # LOAD CSV FILES
    # =========================================================

    print("\nLoading CSV files...")

    patients = pd.read_csv(
        PATIENTS_FILE
    )

    providers = pd.read_csv(
        PROVIDERS_FILE
    )

    appointments = pd.read_csv(
        APPOINTMENTS_FILE
    )

    payments = pd.read_csv(
        PAYMENTS_FILE
    )

    print(
        f"Patients:      {len(patients)}"
    )

    print(
        f"Providers:     {len(providers)}"
    )

    print(
        f"Appointments:  {len(appointments)}"
    )

    print(
        f"Payments:      {len(payments)}"
    )

    # =========================================================
    # REQUIRED COLUMNS
    # =========================================================

    patient_columns = [
        "patient_id",
        "patient_number",
        "first_name",
        "last_name",
        "date_of_birth",
        "gender",
        "phone",
        "email",
        "city",
        "state",
        "zip_code",
        "registration_date",
        "insurance_provider",
        "insurance_id",
        "primary_insurance_code",
        "patient_status",
        "created_at",
        "updated_at",
    ]

    provider_columns = [
        "provider_id",
        "provider_code",
        "first_name",
        "last_name",
        "specialization",
        "department",
        "license_number",
        "phone",
        "email",
        "hospital_name",
        "city",
        "state",
        "zip_code",
        "location_code",
        "hire_date",
        "years_of_experience",
        "provider_status",
        "created_at",
        "updated_at",
    ]

    appointment_columns = [
        "appointment_id",
        "appointment_number",
        "patient_id",
        "provider_id",
        "hospital_name",
        "city",
        "state",
        "zip_code",
        "location_code",
        "procedure_code",
        "procedure_name",
        "procedure_category",
        "standard_duration_minutes",
        "standard_charge",
        "appointment_date",
        "appointment_time",
        "appointment_status",
        "check_in_time",
        "completed_time",
        "cancelled_at",
        "cancellation_reason",
        "reason",
        "diagnosis",
        "notes",
        "created_at",
        "updated_at",
    ]

    payment_columns = [
        "payment_id",
        "payment_number",
        "appointment_id",
        "patient_id",
        "claim_number",
        "amount",
        "allowed_amount",
        "insurance_amount",
        "patient_amount",
        "payment_method",
        "payment_type",
        "payment_date",
        "payment_status",
        "claim_status",
        "submitted_at",
        "processed_at",
        "transaction_id",
        "currency",
        "created_at",
        "updated_at",
    ]

    validate_required_columns(
        patients,
        "patients",
        patient_columns,
        results
    )

    validate_required_columns(
        providers,
        "providers",
        provider_columns,
        results
    )

    validate_required_columns(
        appointments,
        "appointments",
        appointment_columns,
        results
    )

    validate_required_columns(
        payments,
        "payments",
        payment_columns,
        results
    )

    # =========================================================
    # PRIMARY KEY CHECKS
    # =========================================================

    validate_null_primary_keys(
        patients,
        "patients",
        "patient_id",
        results
    )

    validate_duplicate_ids(
        patients,
        "patients",
        "patient_id",
        results
    )

    validate_null_primary_keys(
        providers,
        "providers",
        "provider_id",
        results
    )

    validate_duplicate_ids(
        providers,
        "providers",
        "provider_id",
        results
    )

    validate_null_primary_keys(
        appointments,
        "appointments",
        "appointment_id",
        results
    )

    validate_duplicate_ids(
        appointments,
        "appointments",
        "appointment_id",
        results
    )

    validate_null_primary_keys(
        payments,
        "payments",
        "payment_id",
        results
    )

    validate_duplicate_ids(
        payments,
        "payments",
        "payment_id",
        results
    )

    # =========================================================
    # APPOINTMENT STATUS
    # =========================================================

    validate_appointment_statuses(
        appointments,
        results
    )

    # =========================================================
    # PAYMENT AMOUNTS
    # =========================================================

    validate_negative_payment_amounts(
        payments,
        results
    )

    # =========================================================
    # REFERENTIAL INTEGRITY
    # =========================================================

    validate_patient_references(
        appointments,
        patients,
        results
    )

    validate_provider_references(
        appointments,
        providers,
        results
    )

    validate_payment_appointment_references(
        payments,
        appointments,
        results
    )

    # =========================================================
    # DATE VALIDATION
    # =========================================================

    validate_dates(
        patients,
        "patients",
        [
            "date_of_birth",
            "registration_date",
            "created_at",
            "updated_at",
        ],
        results
    )

    validate_dates(
        providers,
        "providers",
        [
            "hire_date",
            "created_at",
            "updated_at",
        ],
        results
    )

    validate_dates(
        appointments,
        "appointments",
        [
            "appointment_date",
            "check_in_time",
            "completed_time",
            "cancelled_at",
            "created_at",
            "updated_at",
        ],
        results
    )

    validate_dates(
        payments,
        "payments",
        [
            "payment_date",
            "submitted_at",
            "processed_at",
            "created_at",
            "updated_at",
        ],
        results
    )

    # =========================================================
    # FINANCIAL VALIDATION
    # =========================================================

    validate_financial_consistency(
        payments,
        results
    )

    # =========================================================
    # CREATE VALIDATION REPORT
    # =========================================================

    report_df = pd.DataFrame(
        results
    )

    report_df.to_csv(
        REPORT_FILE,
        index=False
    )

    # =========================================================
    # CALCULATE FINAL STATUS
    # =========================================================

    failed_checks = report_df[
        report_df["status"] == "FAIL"
    ]

    total_errors = int(
        report_df["error_count"].sum()
    )

    overall_status = (
        "PASS"
        if len(failed_checks) == 0
        else "FAIL"
    )

    # =========================================================
    # PRINT SUMMARY
    # =========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "VALIDATION SUMMARY"
    )

    print(
        "=" * 70
    )

    total_checks = len(
        report_df
    )

    passed_checks = len(
        report_df[
            report_df["status"] == "PASS"
        ]
    )

    failed_check_count = len(
        failed_checks
    )

    print(
        f"Total checks:       {total_checks}"
    )

    print(
        f"Passed checks:      {passed_checks}"
    )

    print(
        f"Failed checks:      {failed_check_count}"
    )

    print(
        f"Total validation errors: {total_errors}"
    )

    print(
        f"Validation status:  {overall_status}"
    )

    print(
        f"\nReport: {REPORT_FILE}"
    )

    # =========================================================
    # PRINT FAILED CHECKS
    # =========================================================

    if len(failed_checks) > 0:

        print(
            "\nFAILED CHECKS"
        )

        print(
            "-" * 70
        )

        for _, row in failed_checks.iterrows():

            print(
                f"{row['dataset']} -> "
                f"{row['check_name']} -> "
                f"{row['message']}"
            )

    print(
        "=" * 70
    )

    # =========================================================
    # PIPELINE EXIT STATUS
    # =========================================================

    # Exit with code 1 when validation fails.
    #
    # This is important because run_pipeline.py
    # will use this exit code to stop the pipeline
    # when validation fails.

    if overall_status == "FAIL":
        raise SystemExit(1)


# =============================================================
# PROGRAM ENTRY POINT
# =============================================================

if __name__ == "__main__":
    main()