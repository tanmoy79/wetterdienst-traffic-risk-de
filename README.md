# Weather-Driven Traffic Risk in Germany — wetterdienst edition (`wetterdienst-traffic-risk-de`)

A Snakemake workflow that analyses how weather (precipitation, frost, heat, solar
radiation) relates to traffic accident frequency and severity in Germany,
2020–2024. Accident data comes from the official
[German Accident Atlas (Unfallatlas)](https://unfallatlas.statistikportal.de/),
weather data from the [DWD Climate Data Center](https://opendata.dwd.de/climate_environment/CDC/).

This repository is a fork of
[`weather-driven-traffic-risk-de`](https://github.com/tanmoy79/weather-driven-traffic-risk-de).
The analysis (research questions, statistics, figures, report) is unchanged so
that results stay directly comparable. What is different is the **weather
ingestion layer**.

## What this fork changes

The upstream project pulls DWD observations by parsing the DWD CDC HTML index,
downloading per-station ZIPs, unzipping the product files, and reshaping them
into a tidy table — two scripts and ~300 lines of code:

* `src/download_weather.py`
* `src/prepare_weather.py`

This fork replaces both with a single CLI tool that uses the
[`wetterdienst`](https://github.com/earthobservations/wetterdienst) library:

* `src/fetch_weather.py`

| Concern                       | Upstream                                | This fork                                                       |
| ----------------------------- | --------------------------------------- | --------------------------------------------------------------- |
| Station discovery             | Parse `*_Beschreibung_Stationen.txt`    | `DwdObservationRequest(...).all().df`                           |
| Period coverage filter        | Manual string-date comparison           | Same filter applied on `start_date` / `end_date` columns        |
| Per-state selection           | `groupby('state').head(per_state)`      | Same                                                            |
| Solar preference              | `sort_values(['has_solar', ...])`       | Same                                                            |
| Download mechanism            | `requests.get` + zipfile + CSV parsing  | `request.filter_by_station_id(...).values.all().df`             |
| Missing-value handling        | Replace `-999` with NaN                 | `wetterdienst` does it natively                                 |
| Time-zone conversion          | `tz_localize('UTC').tz_convert('Berlin')` | Same                                                            |
| Pipeline step count           | 2                                       | 1                                                               |
| External HTTP / parsing logic | ~250 lines                              | 0                                                               |

The fork preserves the downstream contract exactly — `data/raw_weather/stations.csv`
and `data/climate/weather_hourly.csv` still have the same columns and units
(temperature in °C, precipitation in mm/h, solar radiation in J/cm²), so
`join_data`, `build_features`, `analyze_rq`, `plot_results` and `make_report`
are byte-for-byte the same.

Notably, the upstream project's own
[`docs/requirements.md`](docs/requirements.md) already lists `wetterdienst` as
the intended implementation for the "Extract hourly weather data (DWD CDC)"
node of the abstract workflow — this fork follows through on that design.

## Research Questions

1. **RQ1** — How do precipitation intensities and frost affect accident frequency, severity and type, and does the effect of adverse-weather road conditions differ between **urban and rural** areas? (Urban/rural comes from a third dataset, the BBSR settlement-structure district types — see below.)
2. **RQ2** — Do summer heat and strong solar radiation raise commuter-hour accident rates compared to rain?
3. **RQ3** — Which German federal states are most weather-sensitive, and how do city states compare to territorial states?
4. **RQ4** — How has the relative risk of weather-related accidents evolved across 2020–2024?

See [`docs/requirements.md`](docs/requirements.md) for the full set, and run the
workflow to produce the result tables and figures in `results/`.

## Installation

Requires Python ≥ 3.10.

```bash
python -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the workflow

The raw accident data (2020–2024) is included in `data/raw_accidents/`. The
weather data is downloaded on the first run via `wetterdienst`, which keeps a
local cache so reruns are fast.

```bash
snakemake --cores 4 -s workflow/Snakefile
```

Each step is also a standalone command-line tool, e.g.:

```bash
python src/fetch_weather.py --start-year 2020 --end-year 2024 \
    --stations-per-state 2 \
    --stations-out data/raw_weather/stations.csv \
    --weather-out data/climate/weather_hourly.csv
```

See `python src/<tool>.py --help` for each step.

### Configuration

All parameters live in [`config/config.yaml`](config/config.yaml): year range,
stations per state, maximum accident-to-station distance, and the thresholds
for rain, heavy rain, frost, heat and strong sun.

## Tests

```bash
pytest tests
```

The tests for the new fetch layer mock the `wetterdienst` client, so they don't
need network access.

## Repository Structure

```
wetterdienst-traffic-risk-de/
├── CITATION.cff
├── CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── requirements.txt
├── .flake8
├── .github/workflows/ci.yml
├── config/config.yaml
├── data/
│   └── raw_accidents/             # Unfallatlas accident records (committed)
├── docs/requirements.md           # Requirements and activity diagram
├── results/                       # Generated output (reproducible)
├── src/
│   ├── prepare_accidents.py       # Merge yearly Unfallatlas files
│   ├── fetch_weather.py           # NEW: wetterdienst-based replacement for
│   │                              #      download_weather + prepare_weather
│   ├── classify_region.py         # Tag accidents urban/rural via BBSR district types
│   ├── join_data.py               # Match accidents to nearest station (KD-tree)
│   ├── build_features.py          # Aggregate into time cells with thresholds
│   ├── descriptive_stats.py       # Summary statistics and overview figures
│   ├── analyze_rq.py              # Statistics per research question
│   ├── plot_results.py            # One figure per research question
│   └── make_report.py             # Assemble results/report.md
├── tests/                         # Pytest unit tests (incl. wetterdienst mocks)
└── workflow/Snakefile             # Snakemake pipeline
```

## Data Sources and Licenses

* **Unfallatlas** — © Statistische Ämter des Bundes und der Länder,
  [Datenlizenz Deutschland – Namensnennung – 2.0](https://www.govdata.de/dl-de/by-2-0).
* **DWD Climate Data Center** — Deutscher Wetterdienst,
  [CC-BY 4.0](https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.pdf),
  accessed through the [wetterdienst](https://github.com/earthobservations/wetterdienst) library.

## Credits

Upstream project (the analysis and workflow this fork is based on):
[`weather-driven-traffic-risk-de`](https://github.com/tanmoy79/weather-driven-traffic-risk-de)
by Nazmul Hasan Tanmoy, Farhana Ahmed and Emmanuel Gomes (University of Potsdam),
part of the Research Software Engineering course taught by Prof. Dr. Anna-Lena
Lamprecht.

## License

[MIT License](LICENSE).
