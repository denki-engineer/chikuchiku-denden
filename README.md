# chikuchiku-denden

A Python and Streamlit application for industrial electricity cost analysis, tariff comparison, and battery scheduling simulation.

![UI](assets/ui_step5.png)

## Overview

`chikuchiku-denden` is a practical simulation tool for evaluating electricity cost reduction scenarios in industrial facilities.

The app focuses on real business workflows:

- comparing tariff plans
- importing messy operational CSV files
- estimating battery impact on peak demand
- simulating charging and discharging schedules
- visualizing monthly and annual cost differences

This repository is published as a portfolio project to demonstrate software engineering, data handling, and business-oriented problem solving in the energy domain.

## Background / Why this project exists

In industrial energy analysis, the hard part is not only the calculation itself.
The real difficulty is turning utility-style data and operational assumptions into a repeatable decision-making workflow.

This project was built to address that gap by combining:

- domain-aware data import
- explicit validation of business input data
- modular simulation logic
- a UI that non-developers can actually use
- Windows executable packaging for distribution

The result is an application that reflects a realistic "electricity x IT x operational improvement" problem, rather than a toy optimization script.

## Key Features

- Compare two electricity tariff plans using 30-minute interval load data
- Calculate annual energy usage, annual peak demand, and annual cost before battery operation
- Estimate battery sizing references from target grid demand assumptions
- Edit monthly battery schedules by operating day and holiday
- Simulate battery charge/discharge behavior across a full year
- Visualize before/after demand and monthly cost impact
- Import practical CSV layouts, including utility-style monthly electricity reports
- Export and import project data as ZIP files
- Build a Windows executable for non-Python users

## Structure

```text
app.py                 Streamlit entry point
ui_components.py       UI rendering and interaction handling
models.py              Data models and validation
io_utils.py            CSV / ZIP import-export and format conversion
calculators.py         Application-facing calculation facade
engine/                Core domain logic
defaults/              Public sample/default data
assets/                Screenshots and README assets
sample_data/           Public example input files for GitHub readers
docs/                  Architecture notes and portfolio-friendly documentation
build_exe.ps1          Windows executable build script
chikuchiku_denden.spec PyInstaller spec
```

## Screenshots

### Battery scheduling UI
![Battery scheduling UI](assets/ui_step5.png)

### Before / after demand graph
![Before after graph](assets/graph_before_after.png)

### Monthly result summary
![Monthly result summary](assets/monthly_result.png)

## How to run

### Run from source

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### Build Windows executable

```powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

The distribution-ready executable folder is prepared under:

```text
release/chikuchiku_denden
```

Run:

```text
release/chikuchiku_denden/chikuchiku_denden.exe
```

## Sample data

This repository includes only public sample data and demonstration defaults.

- `defaults/` contains app-initialization sample files
- `sample_data/` contains public example input files for explanation and testing

No confidential customer data, billing data, or operationally sensitive files are included.

## Disclaimer

This project is a portfolio and demonstration application.

- It is not financial, legal, or contractual advice
- Simulation results are estimates based on simplified assumptions
- Outputs should be validated before real operational use

## License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file.

## Related docs

- [Japanese README](README_ja.md)
- [Architecture note](docs/architecture.md)
- [Sample data note](sample_data/README.md)

## Author

Created by `昭 井上`.
