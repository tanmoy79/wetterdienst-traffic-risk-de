# Requirements

## Project: Weather-Driven Traffic Accident Risk in Germany (2020–2024)

The goal of this project is to combine German traffic accident records (Unfallatlas) with hourly
weather observations from the DWD Climate Data Center to investigate how weather conditions
relate to accident frequency. A third dataset — the BBSR settlement-structure district types —
is joined in to classify each accident location as urban or rural (used by RQ1).




## 1. Functional Requirements

The workflow takes two datasets — accident records and hourly weather data — prepares them
separately, joins them by location and time, and produces statistical results and visualisations
that answer the research questions below.

### Research Questions

- **RQ1 — Urban vs. Rural Vulnerability:** How do varying intensities of precipitation and freezing temperatures impact accident frequency, severity and type, and does the effect of adverse-weather road conditions differ between urban and rural areas? *(The published Unfallatlas has no road-class attribute, so the originally intended Autobahn-vs-Landstraße comparison is replaced by an urban-vs-rural split derived from the BBSR settlement-structure district types.)*
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
| **Prepare accident data** (load, merge, clean) | Raw yearly Unfallorte files in `data/raw_accidents/` (CSV/TXT) | Single cleaned accident CSV (`data/processed/accidents_clean.csv`) | Custom Python CLI — `src/prepare_accidents.py` using `pandas` (per-year reader, concat, cleaning) | Fully runnable locally — no network needed; the raw Unfallorte files are committed in the repo and the script is pure `pandas`. |
| **Classify region** (urban/rural) | Cleaned accident CSV + BBSR district-type reference (`data/reference/bbsr_kreistypen_2020.csv`) | Accident CSV with `region_type` + `region_class` columns (`data/processed/accidents_classified.csv`) | Custom Python CLI — `src/classify_region.py` — builds the 5-digit district key (AGS) and joins the BBSR settlement-structure types | Fully runnable locally — the BBSR reference (3rd dataset) is committed in `data/reference/`; pure `pandas` join. |
| **Fetch & standardize hourly weather data** | Year range, stations-per-state, DWD CDC | Stations CSV (`data/raw_weather/stations.csv`) + gap-free hourly weather CSV (`data/climate/weather_hourly.csv`, Europe/Berlin local time) | Custom Python CLI — `src/fetch_weather.py` wrapping the [`wetterdienst`](https://github.com/earthobservations/wetterdienst) library | Internet connection required on first run to fetch from the DWD Climate Data Center; `wetterdienst` caches downloaded files in `%LocalAppData%\wetterdienst\Cache`, so subsequent runs are offline. |
| **Spatial join (accident → nearest station)** | Classified accident CSV + stations CSV | Accident CSV with `station_id` column (`data/joined/accidents_stations.csv`) | Custom Python CLI — `src/join_data.py` using `scipy.spatial.cKDTree` | Completely runnable locally — pure in-memory KD-tree operation over the previously prepared files. |
| **Build features (analysis table)** | Hourly weather CSV + joined accident CSV + stations CSV + thresholds | Analysis table CSV with one row per time cell (`data/processed/analysis_table.csv`) | Custom Python CLI — `src/build_features.py` using `pandas.groupby` and threshold classification | Fully runnable locally — thresholds come from `config/config.yaml`, all I/O is on local CSVs. |
| **Descriptive statistics & overview plots** | Analysis table + joined accidents | Summary CSV (`results/summary_statistics.csv`) + 2 overview PNGs in `results/figures/` | Custom Python CLI — `src/descriptive_stats.py` using `pandas`, `matplotlib`, `seaborn` | Runnable locally after `pip install -r requirements.txt`; uses a non-interactive matplotlib backend so it also works on headless servers and CI. |
| **Per-RQ statistical analysis (RQ1–RQ4)** | Analysis table + joined accidents + `--rq` wildcard | One result CSV per RQ (`results/rq{rq}_results.csv`) | Custom Python CLI — `src/analyze_rq.py` using `scipy.stats` (rate ratios, chi-square, correlation, trend) | Fully runnable locally — pure statistics on the local analysis table; deterministic for reproducibility. |
| **Per-RQ plots** | Per-RQ result CSV + `--rq` wildcard | One PNG per RQ (`results/figures/rq{rq}.png`) | Custom Python CLI — `src/plot_results.py` using `matplotlib` / `seaborn` | Fully runnable locally; reads only the per-RQ result CSV, writes a single PNG. |
| **Assemble final report** | All per-RQ result CSVs + summary CSV + figures | `results/report.md` | Custom Python CLI — `src/make_report.py` (markdown templating) | Fully runnable locally — pure file assembly, no external dependencies beyond the previous stage outputs. |
| **Workflow Orchestration** | `config/config.yaml` + all step inputs/outputs | All final results in `results/` | Snakemake — `workflow/Snakefile` coordinates the steps with dependency tracking and wildcards (`{rq}`) | Yes — `snakemake --cores N -s workflow/Snakefile`; reruns are incremental thanks to file-based dependency tracking. |
