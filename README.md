# chikuchiku-denden

A portfolio project that demonstrates `electricity x software engineering x business problem solving` through an industrial electricity cost analysis and battery scheduling simulator.

![Battery scheduling UI](assets/ui_step5.png)

## Why this project exists

In industrial energy analysis, the difficult part is often not only the formula itself.

The real challenge is turning utility-style CSV files, tariff tables, and operational assumptions into a repeatable workflow that engineers and non-developers can actually use for decision-making.

I built `chikuchiku-denden` to address that gap.

This project focuses on a practical business problem:

- compare electricity tariff plans
- analyze 30-minute interval electricity usage data
- estimate the effect of battery scheduling on peak demand and annual cost
- convert business-oriented CSV formats into structured simulation inputs
- deliver the application as both source code and a Windows executable

Rather than a toy optimization script, this repository is intended to show how domain knowledge, data transformation, simulation design, and user-facing delivery can be combined into a usable application.

## Overview

`chikuchiku-denden` is a Python and Streamlit application for evaluating electricity cost reduction scenarios in industrial facilities.

The app supports a practical workflow:

- compare two tariff plans
- import electricity usage data from business-oriented CSV layouts
- estimate battery sizing references from target demand assumptions
- edit monthly charge and discharge schedules
- simulate annual battery operation and cost impact
- export or re-import projects as ZIP files

## What problem it solves

This application is designed for scenarios such as:

- evaluating whether a facility should change electricity tariff plans
- estimating the cost reduction impact of battery operation
- comparing before-and-after annual cost and peak-demand behavior
- converting messy operational data into reusable simulation inputs
- sharing an analysis tool with users who do not have a Python environment

It is a software project built around a real operational question in the energy domain.

## Key Features

- Compare two electricity tariff plans using 30-minute interval load data
- Calculate annual energy usage, annual peak demand, and annual cost before battery operation
- Estimate battery sizing references from target grid demand assumptions
- Edit battery schedules by month and by operating-day or holiday pattern
- Simulate battery charge and discharge behavior across a full year
- Visualize before-and-after demand and monthly cost impact
- Import practical CSV layouts, including utility-style monthly electricity reports
- Export and import project data as ZIP files
- Build a Windows executable for non-Python users

## Architecture

The codebase is separated into UI, data handling, and domain logic layers.

- `app.py`
  Streamlit entry point
- `ui_components.py`
  UI rendering and interaction flow
- `io_utils.py`
  CSV and ZIP import-export plus format conversion
- `models.py`
  Data structures and validation
- `calculators.py`
  Calculation facade used by the UI
- `engine/`
  Core business and simulation logic

See [docs/architecture.md](docs/architecture.md) for more details.

## Repository Structure

```text
app.py
ui_components.py
io_utils.py
models.py
calculators.py
engine/
defaults/
sample_data/
docs/
assets/
build_exe.ps1
chikuchiku_denden.spec
```

## Sample Input and Output

Public sample files are included in `sample_data/`.

- `sample_energy_usage.csv`
- `sample_tariff.csv`
- `sample_battery_schedule.csv`

Example outputs include:

- annual cost comparison
- monthly savings summary
- before-and-after demand graphs
- editable battery scheduling tables

## Screenshots

### Battery scheduling UI
![Battery scheduling UI](assets/ui_step5.png)

### Before-and-after demand graph
![Before-and-after demand graph](assets/graph_before_after.png)

### Monthly result summary
![Monthly result summary](assets/monthly_result.png)

## How to Run

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

## Public Data Policy

This repository includes only public sample data and demonstration defaults.

- `defaults/` contains app-initialization sample files
- `sample_data/` contains public example input files for explanation and testing

No confidential customer data, billing data, or operationally sensitive files are included.

## Limitations

- This is a portfolio and demonstration application, not a certified commercial product
- Cost calculations depend on input quality and simplified assumptions
- Tariff rules and battery behavior are modeled for evaluation purposes
- Real deployment should include domain validation against actual contracts and operational conditions

## Future Work

- add stronger automated tests for CSV conversion and annual simulation logic
- support easier comparison across multiple battery sizes and operating strategies
- improve reporting export
- add richer validation messages for malformed utility data
- expand architecture and workflow documentation in `docs/`

## Disclaimer

This project is a portfolio and demonstration application.

- It is not financial, legal, or contractual advice
- Simulation results are estimates based on simplified assumptions
- Outputs should be validated before real operational use

## License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file.

## Related Documents

- [Japanese README](README_ja.md)
- [Architecture note](docs/architecture.md)
- [Sample data note](sample_data/README.md)

## Author

Created by `昭 井上`.

