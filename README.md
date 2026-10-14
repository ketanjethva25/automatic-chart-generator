<div align="center">

# 📊 Automatic Chart Generator & Data Explorer
**An Intelligent, Heuristic-Driven Automated Exploratory Data Analysis (EDA) & Visualization Platform**

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Gradio UI](https://img.shields.io/badge/Gradio-6.28.0-orange?logo=gradio&logoColor=white)](https://gradio.app/)
[![Plotly Express](https://img.shields.io/badge/Plotly-Interactive%20Charts-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Single--File%20Standalone-success)](#-project-architecture)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<p align="center">
  <b>Upload any tabular CSV file &mdash; get instant data profiling, comprehensive descriptive statistics, automated intelligent Plotly charts, and an interactive custom visualization studio.</b>
</p>

[Key Features](#-key-features) •
[App Walkthrough](#-application-tabs--walkthrough) •
[Architecture](#-project-architecture) •
[Heuristics Engine](#-chart-selection-heuristics) •
[Quickstart](#-quickstart--installation) •
[Deployment Guide](#-cloud-deployment-render)

---

</div>

## 🌟 Key Features

- **🚀 Zero-Configuration Auto-Charting**:
  Intelligently inspects dataset column relationships and automatically renders up to **12 publication-grade interactive Plotly visualizations** (Line, Bar, Pie, Scatter with Pearson correlation trendlines, Heatmaps, and Distribution Histograms).

- **🛡️ Robust & Fault-Tolerant CSV Ingestion**:
  Automatically sniffs delimiters (`,`, `;`, `\t`, `|`) and handles multiple character encodings (`utf-8`, `utf-8-sig`, `cp1252`, `latin-1`). Gracefully handles binary, corrupted, or empty files without crashing.

- **🧠 Semantic Column Classification**:
  Goes far beyond raw pandas datatypes. Automatically classifies columns into **Numeric**, **Categorical**, **Datetime**, **Identifier**, **Free Text**, **Constant**, or **Empty**, parsing numbers formatted as currency (`$1,250.50`), percentages (`18.5%`), and international date formats.

- **📋 Complete Dataset Profiling & Statistics**:
  Provides instant missing-value diagnostics, uniqueness ratios, memory previews, and a full suite of descriptive summary statistics tailored to column types (`mean`, `std`, `min`, `quartiles`, `max`, `frequencies`).

- **🎨 Interactive Custom Chart Studio**:
  Empowers users to customize X and Y axes, pick from 8 visualization types, and apply dynamic aggregations (`mean`, `sum`, `count`, `min`, `max`, `median`) with built-in sanity checks and helpful error explanations.

- **⚡ Lightweight & Standalone**:
  Engineered as a clean, unified application in **`app.py`**. Zero complex external modules, minimal dependencies, and ready to run locally or deploy to cloud servers in seconds.

---

## 🖥️ Application Tabs & Walkthrough

The web dashboard is organized into four purpose-built tabs:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     📊 Automatic Chart Generator                       │
│  [ Upload CSV File ] ─────────────────────────── Status: ✅ Loaded     │
├───────────────────┬─────────────────────┬─────────────────┬────────────┤
│ 1 · Preview       │ 2 · Statistics      │ 3 · Auto Charts │ 4 · Custom │
└───────────────────┴─────────────────────┴─────────────────┴────────────┘
```

### 1️⃣ Tab 1: Dataset Preview
- **Dataset Overview Card**: Displays total rows, columns, and total missing cells.
- **Data Preview Table**: Interactive view of the first 10 rows with formatted timestamps and clean null representation.
- **Detected Types Table**: Detailed audit table displaying each column's detected semantic kind, original datatype, missing percentage, unique counts, and auto-chart usability status with explanatory notes.

### 2️⃣ Tab 2: Dataset Statistics
- **Descriptive Statistical Summary**: Computes mean, standard deviation, minimum, 25th percentile, median, 75th percentile, and maximum for numeric features.
- **Categorical & Datetime Metrics**: Highlights date spans (`Min`/`Max`) for temporal columns, and primary modal classes (`Top Value` and `Top Count`) for categorical features.

### 3️⃣ Tab 3: Automatic Charts
- Renders an intelligent portfolio of up to **12 interactive Plotly charts** arranged in a responsive 2-column layout.
- Each chart includes human-readable rationale captions explaining *why* the visualization was selected (e.g., *"Scatter plot (strong correlation, r = 0.74)"* or *"Categorical distribution (6 or fewer values) -> pie chart"*).
- Features hover tooltips, box-zoom, pan, lasso select, and one-click PNG export.

### 4️⃣ Tab 4: Custom Chart Studio
- **Control Bar**:
  - **X-axis Selector**: Populated with all valid columns in your dataset.
  - **Y-axis Selector**: Optional secondary measure (or set to `(none)` for single-variable analysis).
  - **Chart Type**: Choose between *Auto*, *Scatter*, *Line*, *Bar*, *Pie*, *Histogram*, *Box*, or *Correlation Heatmap*.
  - **Aggregation Function**: Choose *mean*, *sum*, *count*, *min*, *max*, or *median*.
- **Intelligent Error Shield**: Invalid mathematical or categorical combinations (such as computing a mean of string columns or requesting negative values in a pie chart) provide friendly, actionable feedback instead of crashing.

---

## 🏗️ Project Architecture

The project is structured as a clean, production-ready standalone repository:

```text
automatic-chart-generator/
│
├── app.py              # Main standalone application (Data Processing, Charting & Gradio UI)
├── requirements.txt    # Project dependencies (gradio, pandas, numpy, plotly)
├── sample.csv          # Sample transactional retail dataset (400 rows x 11 columns)
├── .gitignore          # Git configuration
├── LICENSE             # MIT License
└── README.md           # Documentation
```

### Internal Data Flow

```
[ CSV File Upload ]
        │
        ▼
[ load_csv() ] ────────────► Sniff delimiter & encoding; strip whitespace; drop empty rows
        │
        ▼
[ prepare_dataframe() ] ───► Detect column semantic kinds (Numeric / Date / Categorical / ID)
        │                    Parse currency ($) / percentages (%) / timestamps
        │
        ├──────────────────► Generate Column Profile & Summary Statistics (Tabs 1 & 2)
        │
        ▼
[ generate_auto_charts() ] ─► Allocate chart budget across candidate families
        │                    Render responsive Plotly figures (Tab 3)
        │
        ▼
[ build_custom_chart() ] ──► Dynamic aggregation & custom user visualization (Tab 4)
```

---

## 🎯 Chart Selection Heuristics

The application executes deterministic data-profiling rules to select the best chart type:

| Semantic Combination | Heuristic Decision | Rendered Plotly Chart |
| :--- | :--- | :--- |
| **Datetime × Numeric** | Trend over time (auto-binned if >200 timestamps) | **Line Chart** with responsive markers |
| **Categorical (≤ 6 classes)** | Proportion of parts to whole | **Donut / Pie Chart** |
| **Categorical (> 6 classes)** | Frequency or measure distribution | **Horizontal / Vertical Bar Chart** |
| **Numeric × Numeric** | Correlated pairs ($$\|r\| \ge 0.3$$) | **Scatter Plot** with linear trendline & categorical color hue |
| **Multiple Numerics ($\ge 2$)** | Global feature interdependence | **Correlation Heatmap** ($$-1.0$$ to $$+1.0$$ Pearson $$r$$) |
| **Single Numeric** | Distribution, skewness, and outliers | **Histogram** with marginal Box Plot |
| **Category × Category** | Cross-tabulation of discrete frequencies | **Stacked Bar Chart** |

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python **3.10+** (Tested on Python 3.12, 3.13, and 3.14)
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/automatic-chart-generator.git
cd automatic-chart-generator
```

### 3. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Launch the Application
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:7860
```
Drag and drop `sample.csv` (provided in the root directory) to explore all features instantly!

---

## ☁️ Cloud Deployment (Render)

You can deploy this application for free on [Render](https://render.com/):

1. Push your repository to **GitHub**.
2. Log in to [Render Dashboard](https://dashboard.render.com/) and click **New + ➔ Web Service**.
3. Connect your GitHub repository `automatic-chart-generator`.
4. Configure service settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python app.py`
   - **Instance Type:** `Free`
5. Click **Deploy Web Service**. Your app will be live on a public URL (e.g. `https://automatic-chart-generator.onrender.com`).

---

## 📦 Dependencies

The application relies strictly on battle-tested core data science and web libraries:

```text
gradio==6.28.0
pandas>=2.1
numpy>=1.24
plotly>=5.18
```

---

## 🤝 Contributing

Contributions, issues, and feature suggestions are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

<div align="center">
  <sub>Built with ❤️ using Python, Gradio, Pandas, and Plotly.</sub>
</div>
