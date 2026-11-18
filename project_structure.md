# Project Structure

- `aml/` — the pipeline package: configuration, IO, cleaning, feature engineering, monitoring rules, customer scoring, reporting and the CLI.
- `config/` — example configuration file documenting every tunable threshold.
- `data/raw/` — synthetic source datasets.
- `data/processed/` — cleaned, feature-engineered and risk-scored datasets.
- `sql/` — schema, cleaning, feature engineering and analysis queries.
- `src/` — thin wrappers that keep the original `python src/<script>.py` commands working.
- `reports/` — sample alert report, alert summary, rule breakdown and the data quality record.
- `tests/` — pytest suite covering the package and the documented commands.
- `dashboard/` — Tableau dashboard build guide.
- `notebooks/` — reserved for exploratory analysis.
- `pyproject.toml` — packaging, the `aml-risk` console script and pytest configuration.
