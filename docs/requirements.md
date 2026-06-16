# Requirements

## Project: Weather-Driven Traffic Accident Risk in Germany (2020–2024)

The goal of this project is to combine German traffic accident records (Unfallatlas) with hourly
weather observations from the DWD Climate Data Center to investigate how weather conditions
relate to accident frequency.




## 1. Functional Requirements

The workflow takes two datasets — accident records and hourly weather data — prepares them
separately, joins them by location and time, and produces statistical results and visualisations
that answer the research questions below.

### Research Questions

- **RQ1 — Infrastructure Vulnerability:** How do varying intensities of precipitation and freezing temperatures differentially impact accident frequency and severity on German Autobahns compared to rural roads (*Landstraßen*)?
- **RQ2 — Summer Sun Threat:** To what extent do summer weather factors — specifically solar radiation (sun glare) and extreme heatwaves — predict commuter-hour accident rates compared to rainy conditions?
- **RQ3 — Spatial Sensitivity:** Which German federal states exhibit the strongest sensitivity of accident patterns to changing weather conditions, and how does this differ between urbanised and rural states?
- **RQ4 — Temporal Evolution:** How have traffic safety patterns evolved under varying weather conditions in Germany between 2020 and 2024, and has the relative risk of weather-related accidents declined due to modern vehicle safety technology?

### Abstract Workflow (UML Activity Diagram)

![Activity Diagram](activity_diagram_updated.png)




## 2. Non-Functional Requirements

1. The project shall run without problems given that all required dependencies are installed properly.
2. The total execution time of the whole project (from reading the raw data to outputting the final results) shall be completed under a reasonable time on a standard laptop.
3. The whole project shall be idempotent — running it multiple times should produce identical output results and visualisations.
4. The project shall support adding more data (additional years or weather parameters) without requiring major code changes.
5. Each step of the workflow shall be a standalone script with clear inputs and outputs, so that individual steps can be re-run independently.
6. Errors (e.g. missing files, API failures, invalid data) shall produce a clear message rather than silently failing.

 

## 3. Abstract Workflow Component Table

| **Abstract Workflow Node (Operation)** | **Input(s)** | **Output(s)** | **Implementation** | **Runnable locally?** |
|---|---|---|---|---|
| **Prepare accident data** (load, merge, clean) | Raw yearly Unfallorte files in `data/raw_accidents/` (CSV/TXT) | Single cleaned accident CSV (`data/processed/accidents_clean.csv`) | Custom Python CLI — `src/prepare_accidents.py` using `pandas` (per-year reader, concat, cleaning) | Yes — pure Python, no network |
| **Fetch & standardize hourly weather data** | Year range, stations-per-state, DWD CDC | Stations CSV (`data/raw_weather/stations.csv`) + gap-free hourly weather CSV (`data/climate/weather_hourly.csv`, Europe/Berlin local time) | Custom Python CLI — `src/fetch_weather.py` wrapping the [`wetterdienst`](https://github.com/earthobservations/wetterdienst) library | Yes — needs internet on first run; wetterdienst caches downloads afterwards |
| **Spatial join (accident → nearest station)** | Cleaned accident CSV + stations CSV | Accident CSV with `station_id` column (`data/joined/accidents_stations.csv`) | Custom Python CLI — `src/join_data.py` using `scipy.spatial.cKDTree` | Yes — pure Python |
| **Build features (analysis table)** | Hourly weather CSV + joined accident CSV + stations CSV + thresholds | Analysis table CSV with one row per time cell (`data/processed/analysis_table.csv`) | Custom Python CLI — `src/build_features.py` using `pandas.groupby` and threshold classification | Yes — pure Python |
| **Descriptive statistics & overview plots** | Analysis table + joined accidents | Summary CSV (`results/summary_statistics.csv`) + 2 overview PNGs in `results/figures/` | Custom Python CLI — `src/descriptive_stats.py` using `pandas`, `matplotlib`, `seaborn` | Yes |
| **Per-RQ statistical analysis (RQ1–RQ4)** | Analysis table + joined accidents + `--rq` wildcard | One result CSV per RQ (`results/rq{rq}_results.csv`) | Custom Python CLI — `src/analyze_rq.py` using `scipy.stats` (rate ratios, chi-square, correlation, trend) | Yes |
| **Per-RQ plots** | Per-RQ result CSV + `--rq` wildcard | One PNG per RQ (`results/figures/rq{rq}.png`) | Custom Python CLI — `src/plot_results.py` using `matplotlib` / `seaborn` | Yes |
| **Assemble final report** | All per-RQ result CSVs + summary CSV + figures | `results/report.md` | Custom Python CLI — `src/make_report.py` (markdown templating) | Yes |
| **Workflow Orchestration** | `config/config.yaml` + all step inputs/outputs | All final results in `results/` | Snakemake — `workflow/Snakefile` coordinates the steps with dependency tracking and wildcards (`{rq}`) | Yes — `snakemake --cores N -s workflow/Snakefile` |
