<div align="center">

# 📊 Automatic Chart Generator

**A smart, easy-to-use web application that automatically analyzes CSV data and builds interactive charts without writing code.**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/Gradio-6.28.0-FF7C00?style=for-the-badge&logo=gradio&logoColor=white)](https://gradio.app/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/)
[![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![License](https://img.shields.io/badge/License-MIT-2ea44f?style=for-the-badge)](LICENSE)

<br/>

[Overview](#-overview) •
[Key Features](#-key-features) •
[Application Walkthrough](#-application-walkthrough) •
[How It Works](#-how-it-works) •
[Project Structure](#-project-structure) •
[Quickstart](#-quickstart--run-locally) •
[Deploy Online](#-free-cloud-deployment-render)

---

</div>

## 📖 Overview

In data science, analysts spend a lot of time writing repetitive Python code just to preview data, check missing values, and draw basic charts.

**Automatic Chart Generator** solves this with a single click. Just upload any standard CSV file, and the application will:
1. Automatically clean the data and detect column types (numbers, dates, categories, text).
2. Calculate key summary statistics (mean, median, min, max, missing values).
3. Generate up to **12 relevant, interactive charts** using smart built-in rules.
4. Let you design your own **custom charts** using simple dropdowns.

Everything runs from a single, clean file (`app.py`) with an intuitive web dashboard.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| ⚡ **Automatic Charting** | Creates up to 12 publication-ready interactive Plotly charts instantly on upload. |
| 🧹 **Smart Data Cleaning** | Detects delimiters (`,`, `;`, tab, `|`) and cleans formatted numbers like `$1,500` or `20%`. |
| 🔍 **Type Detection** | Categorizes columns into Numbers, Dates, Categories, Text, or IDs automatically. |
| 📊 **Descriptive Statistics** | Calculates counts, mean, standard deviation, quartiles, and min/max values. |
| 🛠️ **Custom Chart Studio** | Pick your own X-axis, Y-axis, chart type, and calculation method (sum, mean, count, etc.). |
| 💡 **Interactive & Exportable** | Zoom, pan, hover for exact data tooltips, and download any chart as a high-resolution PNG. |
| 🛡️ **Error-Safe** | Displays clear, friendly messages if an invalid column combination is selected. |

---

## 🖥️ Application Walkthrough

The web interface is divided into **4 intuitive tabs**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                     📊 Automatic Chart Generator                       │
│  [ Upload CSV File ] ─────────────────────────── Status: ✅ Loaded     │
├───────────────────┬─────────────────────┬─────────────────┬────────────┤
│ 1 · Preview       │ 2 · Statistics      │ 3 · Auto Charts │ 4 · Custom │
└───────────────────┴─────────────────────┴─────────────────┴────────────┘
```

### 1️⃣ Tab 1: Dataset Preview
- **Overview Summary**: Displays filename, total row count, column count, and total missing cells.
- **First 10 Rows Table**: Quick spreadsheet-like view of your actual data.
- **Column Audit Table**: Shows each column's detected type, missing percentage, unique values count, and whether it can be charted.

### 2️⃣ Tab 2: Dataset Statistics
- Shows clean summary statistics tailored to each column type:
  - **Numeric columns**: Count, Mean, Std, Min, 25%, Median, 75%, and Max.
  - **Date columns**: Earliest and latest timestamps.
  - **Categorical columns**: Most frequent item and frequency count.

### 3️⃣ Tab 3: Automatic Charts
- Displays up to **12 smart Plotly charts** organized in a 2-column responsive layout.
- Every chart includes an informative subtitle explaining **why** it was chosen (e.g., *"Scatter plot: strong correlation (r = 0.74)"* or *"Line chart: trend over date"*).

### 4️⃣ Tab 4: Custom Chart Studio
- Build your own charts on demand:
  - **X-axis**: Select any column.
  - **Y-axis**: Select a numerical value (or choose `(none)` for single-column charts).
  - **Chart Type**: Auto, Scatter, Line, Bar, Pie, Histogram, Box, or Correlation Heatmap.
  - **Aggregation**: Mean, Sum, Count, Min, Max, or Median.

---

## 🎯 How It Works

The app uses smart, deterministic rules to select the most meaningful chart for your data:

```text
[ CSV Upload ] ──► [ Clean & Detect Types ] ──► [ Calculate Stats ] ──► [ Generate Charts ]
```

| If your columns are... | The app automatically creates a... | Why this chart? |
| :--- | :--- | :--- |
| **Date + Number** | **Line Chart** | Perfect for tracking trends, changes, and growth over time. |
| **Category (2 to 6 values)** | **Pie / Donut Chart** | Clearly displays percentage share of a whole. |
| **Category (> 6 values)** | **Bar Chart** | Easily compares values across multiple categories without clutter. |
| **Two Numeric Columns** | **Scatter Plot** | Shows relationships, correlations, and trendlines between numbers. |
| **Multiple Numeric Columns** | **Correlation Heatmap** | Shows mutual correlation between all numeric features at a glance. |
| **Single Numeric Column** | **Histogram + Box Plot** | Shows data distribution, spread, frequency, and outliers. |

---

## 📁 Project Structure

The project is built as a clean, single-file application:

```text
automatic-chart-generator/
│
├── app.py              # Complete standalone application (Data Processing + Charts + Gradio UI)
├── requirements.txt    # Project dependencies
├── sample.csv          # Sample retail dataset for testing (400 rows x 11 columns)
├── .gitignore          # Git configuration
├── LICENSE             # MIT License
└── README.md           # Documentation
```

---

## 🚀 Quickstart & Run Locally

### 1. Prerequisites
- **Python 3.10 or higher** installed on your system.

### 2. Clone the Repository
```bash
git clone https://github.com/ketanjethva25/automatic-chart-generator.git
cd automatic-chart-generator
```

### 3. Create a Virtual Environment (Recommended)
```bash
# On Windows:
python -m venv .venv
.venv\Scripts\activate

# On macOS / Linux:
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

Open your browser and visit:
```text
http://127.0.0.1:7860
```
Upload the included `sample.csv` file to test all features immediately!

---

## ☁️ Free Cloud Deployment (Render)

You can easily host this application online for free on [Render](https://render.com/):

1. Push your repository to **GitHub**.
2. Go to [Render Dashboard](https://dashboard.render.com/) and click **New + ➔ Web Service**.
3. Select and connect your `automatic-chart-generator` repository.
4. Set the following options:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python app.py`
   - **Instance Type:** `Free`
5. Click **Deploy Web Service**. You will receive a permanent live URL (e.g., `https://automatic-chart-generator.onrender.com`).

---

## 🛠️ Built With

- **Python 3** – Core programming language
- **Gradio** – Modern, responsive web user interface
- **Pandas & NumPy** – Robust data cleaning and statistical computation
- **Plotly Express & Graph Objects** – Interactive, publication-ready data visualizations

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

<div align="center">
  <sub>Built with clean code and practical data logic for fast, interactive data exploration.</sub>
</div>
