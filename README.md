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

These results are based on synthetic data and illustrative monitoring rules.

## 7. Repository Structure

```text
aml-transaction-risk-analytics/
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
│   └── sample_alert_report.csv
│
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_data_cleaning.sql
│   ├── 03_feature_engineering.sql
│   └── 04_risk_analysis.sql
│
├── src/
│   ├── customer_risk.py
│   ├── data_cleaning.py
│   ├── feature_engineering.py
│   ├── fraud_detection.py
│   └── generate_alert_report.py
│
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

### Step 2: Clean the datasets

```bash
python src/data_cleaning.py
```

### Step 3: Generate analytical features

```bash
python src/feature_engineering.py
```

### Step 4: Run transaction monitoring

```bash
python src/fraud_detection.py
```

### Step 5: Generate customer risk scores

```bash
python src/customer_risk.py
```

### Step 6: Generate alert reports

```bash
python src/generate_alert_report.py
```

Generated outputs are written to the relevant `data/processed/` and `reports/` directories.

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
