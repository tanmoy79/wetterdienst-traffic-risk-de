# Contributing to Weather-Driven Traffic Risk in Germany (`wetterdienst-traffic-risk-de`)

Thank you for your interest in contributing! This fork focuses on a cleaner
weather-data ingestion layer (via [wetterdienst](https://github.com/earthobservations/wetterdienst))
on top of the same Unfallatlas-based traffic accident analysis. Analytical
improvements, pipeline optimizations, and bug fixes are all welcome.

---

## Code of Conduct
Please adhere to the Contributor Covenant Code of Conduct in all interactions
within this project. See [CONDUCT.md](CONDUCT.md).

---

## Getting set up

```bash
python -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install flake8
pytest tests
flake8 src tests
snakemake -n -s workflow/Snakefile
```

## Coming soon
