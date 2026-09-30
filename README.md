# Clinic Data Engineering Pipeline

An end-to-end, batch-driven data engineering pipeline that generates synthetic clinic data, validates it, loads it into raw and core layers, runs automated quality checks, and produces run reports. The project also includes a serverless AWS architecture (S3, Lambda, IAM, Glue, Data Catalog, Athena) for running the same ETL flow in the cloud.

## Features

- **Synthetic data generation** using Python and Faker
- **Data validation** before anything is loaded
- **Layered loading:** raw layer first, then a transformed core layer
- **Automated data quality checks** that stop the pipeline if any check fails
- **Batch tracking:** every run gets a unique batch ID (`BATCH_<timestamp>_<id>`)
- **Centralized configuration** (YAML) and **logging** (`logs/pipeline.log`)
- **Detailed and summary reports** generated at the end of each run
- **Modular design:** each stage is its own class under `src/`

## Pipeline Flow

```
Step 1  Data Generation        -> synthetic clinic data
Step 2  Data Validation        -> schema and value checks
Step 3  Raw Data Load          -> raw layer
Step 4  Transformation + Load  -> cleaned core layer
Step 5  Quality Check          -> pipeline halts if checks fail
Step 6  Report Generation      -> detailed + summary reports
```

## Tech Stack

| Area | Tools |
|------|-------|
| Language | Python |
| Data handling | Pandas, Faker |
| Database | PostgreSQL (psycopg2) |
| Configuration | PyYAML |
| Cloud (AWS) | S3, Lambda, IAM, Glue, Glue Data Catalog, Athena |

## Project Structure

```
.
├── data/                    # Generated and sample data
├── docs/                    # Documentation
├── src/
│   ├── config/              # Configuration manager
│   ├── database/            # Database connection manager
│   ├── ingestion/           # Data generator and raw loader
│   ├── pipeline/            # Pipeline context and logger
│   ├── quality/             # Validator and quality checker
│   ├── transformation/      # Transformation logic
│   └── reporting/           # Report generator
├── check_schema.py
├── generate_sample_data.py
├── load_raw_data.py
├── validate_data.py
├── run_pipeline.py          # Main entry point
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.9+
- A running PostgreSQL instance

### Installation

```bash
git clone https://github.com/HariVardhan-51/Software.git
cd Software
pip install -r requirements.txt
```

### Configure

Update the YAML configuration with your database connection details and file paths before running.

### Run the full pipeline

```bash
python run_pipeline.py
```

On success, the console shows the batch ID, status, duration, quality check results, and both reports. On failure, it prints the error and points to `logs/pipeline.log`.

### Run individual stages

```bash
python generate_sample_data.py   # generate synthetic data
python validate_data.py          # validate generated data
python load_raw_data.py          # load into the raw layer
python check_schema.py           # verify the database schema
```

## AWS Architecture

The same flow runs serverlessly on AWS:

```
Synthetic data
     |
     v
Amazon S3 (raw)  --upload event-->  AWS Lambda
                                        |
                                        v
                    AWS Glue Crawler -> Glue Data Catalog
                                        |
                                        v
                          AWS Glue ETL job (PySpark)
                       validate, clean, quality checks
                                        |
                                        v
                        Amazon S3 (processed, Parquet)
                                        |
                                        v
                                  Amazon Athena
                            SQL queries and reports
```

| Service | Role in the pipeline |
|---------|----------------------|
| **Amazon S3** | Stores raw data and processed Parquet output |
| **AWS Lambda** | Triggers the pipeline automatically when new data lands in S3 |
| **IAM roles** | Least-privilege permissions for Lambda, Glue, S3, and Athena |
| **AWS Glue Crawlers** | Detect schema and register raw and processed datasets |
| **Glue Data Catalog** | Central metadata store queried by Glue and Athena |
| **AWS Glue ETL job** | PySpark job that cleans, validates, and transforms the data |
| **Amazon Athena** | Runs SQL on the processed data for insights and reports |

## Future Improvements

- Add unit tests for the validator and quality checker
- Schedule runs with EventBridge
- Add alerting for failed quality checks
- Add a dashboard on top of the Athena tables

## Author

**Hari Vardhan Reddy Kotu**
B.Tech in Data Science, KHIT Guntur
[LinkedIn](https://linkedin.com/in/hari-vardhan-reddy-kotu-519a08300) | [GitHub](https://github.com/Harivardhan51)