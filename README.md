# AML Transaction Risk Analytics Platform

A Python-based portfolio project demonstrating data preparation, transaction monitoring, rule-based suspicious activity detection, customer risk profiling, and compliance-oriented analytics using Python, Pandas, NumPy, and SQL.

> **Data notice:** All datasets are synthetic and generated for educational and portfolio purposes. No real customer, banking, or personally identifiable financial data is included.

## 1. Project Overview

The objective of this project is to develop an analytical workflow that demonstrates how financial transaction data can be processed to identify potentially suspicious patterns and generate risk-oriented insights.

The platform brings together synthetic customer, transaction, bank, and geographic-risk datasets to:

- Integrate data from multiple sources.
- Clean and validate transaction records.
- Engineer transaction-level and customer-level risk indicators.
- Identify potentially suspicious transaction patterns using transparent, rule-based logic.
- Generate investigation-oriented alerts and risk summaries.
- Support compliance analytics through structured datasets and SQL queries.

## 2. Technology Stack

| Technology | Application |
|---|---|
| Python | Data processing and analytical workflows |
| Pandas | Data manipulation and analysis |
| NumPy | Numerical operations |
| SQL | Relational modelling and risk-oriented queries |
| PostgreSQL | Database implementation, CSV data import, analytical views and risk-oriented SQL queries |
| Jupyter Notebook | Exploratory analysis and documentation |
| `aml` package | Installable pipeline library with tuned thresholds, a CLI and a pytest suite |

## 3. Project Architecture

```text
Synthetic Raw Datasets
        |
        v
Data Cleaning and Validation
        |
        v
Feature Engineering
        |
        +----------------------+
        |                      |
        v                      v
Customer Risk Features   Transaction Features
        |                      |
        +----------+-----------+
                   |
                   v
          Rule-Based Monitoring
                   |
                   v
          Suspicious Transaction Alerts
                   |
                   v
          Risk Summaries and Reports
```

## 4. Dataset Overview

The project uses four synthetic input datasets:

| Dataset | Description |
|---|---|
| customers.csv | Customer profiles, customer type, KYC status and PEP indicators |
| transactions.csv | Transaction-level activity, amounts, channels and counterparties |
| banks.csv | Bank information and synthetic compliance indicators |
| locations.csv | Geographic information and synthetic country-risk scores |

The datasets contain 300 synthetic customers and 6,182 synthetic transactions, along with 12 banks and 20 locations.

## 5. Illustrative Transaction Monitoring Rules

The project explores transparent, rule-based monitoring scenarios, including:

1. **High-value transactions:** Transactions at or above an illustrative threshold of 10,000.
2. **Near-threshold cash deposits:** Cash deposits between 7,000 and 9,999.99.
3. **High-risk jurisdictions:** Transactions associated with locations assigned higher synthetic risk scores.
4. **Transaction velocity:** Unusually frequent transactions within a one-hour window.
5. **PEP-related activity:** Elevated transactions involving customers with a synthetic PEP indicator.

These rules demonstrate possible financial crime monitoring scenarios. They are illustrative portfolio logic, not regulatory thresholds, confirmed suspicious activity, or a production AML system.

## 6. Analytical Results

The generated analytical summary contains:

| Risk tier | Alert count |
|---|---:|
| High | 55 |
| Medium | 35 |
| **Total** | **90** |

The workflow also produces:

- Cleaned customer and transaction datasets.
- Customer-level risk features.
- Transaction-level analytical features.
- Suspicious transaction alert records.
- Aggregated alert summaries.
- A rule breakdown (`reports/rule_hits.csv`) showing how often each rule fired.
- A data quality record (`reports/data_quality.json`) with kept and dropped rows, referential integrity checks and alert rates.

These results are based on synthetic data and illustrative monitoring rules.

## 7. Repository Structure

```text
aml-transaction-risk-analytics/
│
├── aml/                          # installable pipeline package
│   ├── config.py                 # thresholds, weights, risk tiers, TOML/JSON loading
│   ├── io.py                     # CSV helpers with the repository's CRLF convention
│   ├── cleaning.py               # cleaning plus a row-by-row drop report
│   ├── features.py               # customer and transaction features
│   ├── rules.py                  # monitoring rules, risk score, alert extraction
│   ├── scoring.py                # customer risk scores and the top-N view
│   ├── reporting.py              # alert summary, rule breakdown, data quality
│   ├── pipeline.py               # step orchestration
│   └── cli.py                    # the aml-risk command
│
├── config/
│   └── analysis.toml             # example configuration, every key documented
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── README.md
│
├── notebooks/
│   └── aml_transaction_analysis.ipynb
│
├── reports/
│   ├── alert_summary.csv
│   ├── data_quality.json
│   ├── rule_hits.csv
│   └── sample_alert_report.csv
│
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_data_cleaning.sql
│   ├── 03_feature_engineering.sql
│   └── 04_risk_analysis.sql
│
├── src/                          # thin wrappers around aml, commands unchanged
│   ├── customer_risk.py
│   ├── data_cleaning.py
│   ├── feature_engineering.py
│   ├── fraud_detection.py
│   └── generate_alert_report.py
│
├── tests/                        # pytest suite
│
├── pyproject.toml
├── project_manifest.json
├── project_structure.md
├── requirements.txt
├── LICENSE
└── README.md
```

## 8. Running the Python Workflow

### Step 1: Install dependencies

```bash
pip install -r requirements.txt
```

Install the package if you want the `aml-risk` command and the test tooling:

```bash
pip install -e ".[dev]"
```

### Step 2: Run the whole pipeline

```bash
aml-risk all
```

The command cleans the raw datasets, rebuilds the features, applies the monitoring rules, scores customers and refreshes the reports. Each step can also be run on its own:

```bash
aml-risk clean
aml-risk features
aml-risk monitor
aml-risk score
aml-risk report
```

`aml-risk report --top 5` also prints the five highest scoring customers.

### Step 3: Or run the original scripts

The documented scripts from earlier versions are kept as thin wrappers, so this sequence still works and produces exactly the same files:

```bash
python src/data_cleaning.py
python src/feature_engineering.py
python src/fraud_detection.py
python src/customer_risk.py
python src/generate_alert_report.py
```

Generated outputs are written to the relevant `data/processed/` and `reports/` directories. Runs are reproducible: a second run produces byte-identical files.

### Step 4: Tune the thresholds

Every threshold, weight and risk tier lives in one configuration object. Copy `config/analysis.toml`, edit what you need and pass it in:

```bash
aml-risk all --config config/analysis.toml
```

Keys that are not mentioned keep their defaults, and an unknown key is rejected with the list of accepted names, so a typo cannot silently disable a rule. A JSON file works the same way. For example, to raise the high-value threshold and lower the alert score:

```toml
[rules]
high_value_threshold = 20000.0
alert_threshold = 25.0
```

### Step 5: Run the tests

```bash
python -m pytest
```

The suite covers the configuration rules, the cleaning accounting, the feature windows, every monitoring rule at its boundary, the customer scoring bands, the report ordering, the pipeline end to end and the CLI. It runs against the committed synthetic datasets and pins the published numbers: 6,182 cleaned transactions, 90 alerts (55 High, 35 Medium) and 300 scored customers.

## 9. SQL Analytics

The repository includes PostgreSQL-oriented SQL scripts covering:

- Relational table creation.
- Primary and foreign key relationships.
- Data cleaning and validation.
- Transaction and customer-level feature engineering.
- Risk-oriented analytical queries.

The SQL scripts were executed and tested in PostgreSQL 18 using the synthetic project datasets.

## 10. Project Scope and Limitations

This project is an educational portfolio demonstration, not a production financial crime monitoring solution.

A production implementation would require:

- Institution-specific policies and regulatory requirements.
- Validated monitoring rules and thresholds.
- Reliable sanctions and PEP data sources.
- Model and rule governance.
- False-positive analysis.
- Case management and investigation workflows.
- Audit trails and access controls.
- Ongoing monitoring and periodic validation.

## 11. Future Enhancements

Potential extensions include:

- SQL query optimisation and performance analysis.
- Interactive Tableau dashboards.
- Machine learning-based anomaly detection.
- Explainable customer and transaction risk scoring.
- Graph-based analysis of relationships between customers and counterparties.
- AI-assisted alert summarisation and investigation support.

These are proposed enhancements, not currently implemented project features.

## Author

**Amruta Lopes**

GitHub: [AmrutaLopes](https://github.com/AmrutaLopes)

---

*This project demonstrates practical exploration of data analytics, transaction monitoring, customer risk profiling, and compliance-oriented analytical workflows.*
