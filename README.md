# 📊 Automatic Chart Generator & Data Explorer

A beginner-friendly and smart web application that automatically analyzes CSV datasets and creates interactive charts without writing any code.

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/Gradio-Web%20UI-orange.svg?logo=gradio&logoColor=white)](https://gradio.app/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive%20Charts-3F4F75.svg?logo=plotly&logoColor=white)](https://plotly.com/)
[![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458.svg?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 About The Project

When working with data, developers and data analysts usually write many lines of Python code using Pandas, Matplotlib, or Seaborn just to see basic charts, check missing values, and calculate statistics.

**Automatic Chart Generator** solves this problem. You simply upload any CSV file, and the application will:
1. Clean the data and detect column types (Numbers, Categories, Dates, Text, IDs).
2. Show summary statistics and missing values.
3. Automatically choose and build the best interactive charts for your dataset.
4. Let you create your own custom charts using simple dropdowns.

Everything is packed inside a single standalone Python file (`app.py`), making it very easy to understand, run, and deploy.

---

## ✨ Features

- **Automatic Chart Creation**: Generates up to 12 smart interactive charts (Line, Bar, Pie, Scatter, Heatmap, and Histogram) based on your data.
- **Smart Data Detection**: Automatically identifies dates, categories, numbers, and text. Cleans formatted numbers like `$1,200` or `15%`.
- **Dataset Overview & Statistics**: Displays total rows, columns, missing values, mean, median, standard deviation, and min/max values.
- **Custom Chart Studio**: Lets you pick X-axis, Y-axis, chart type, and calculation type (mean, sum, count, min, max, median).
- **Interactive Visualizations**: Hover over any chart to see exact numbers, zoom in/out, pan, and download charts as PNG images.
- **Error-Proof**: If you select columns that cannot be combined, it shows a friendly explanation instead of crashing.

---

## 🖥️ Application Walkthrough (4 Tabs)

The application has 4 simple tabs:

### 1. Dataset Preview
- Shows the total rows, columns, and missing values.
- Displays an interactive table of the first 10 rows.
- Lists all columns with their detected data type and whether they are suitable for charts.

### 2. Dataset Statistics
- Shows descriptive statistics for every column.
- For numbers: count, mean, standard deviation, min, 25%, median, 75%, and max.
- For dates: earliest and latest dates.
- For categories: most frequent item and its count.

### 3. Automatic Charts
- Automatically selects and displays up to 12 relevant Plotly charts in a clean 2-column grid.
- Each chart has a title and a simple note explaining why that chart was chosen.

### 4. Custom Chart
- Allows you to build your own chart:
  - **X-axis**: Pick any column.
  - **Y-axis**: Pick a value column (optional).
  - **Chart Type**: Choose from Auto, Scatter, Line, Bar, Pie, Histogram, Box, or Heatmap.
  - **Aggregation**: Choose mean, sum, count, min, max, or median.

---

## 🎯 How the App Chooses Charts Automatically

The system follows simple logic rules based on the columns in your data:

| Column Types in Data | Chart Chosen | Reason |
| :--- | :--- | :--- |
| **Date + Number** | **Line Chart** | Best for showing changes and trends over time. |
| **Category (2 to 6 values)** | **Pie / Donut Chart** | Best for showing percentage shares of a whole. |
| **Category (more than 6 values)** | **Bar Chart** | Best for comparing values across multiple items clearly. |
| **Two Numeric Columns** | **Scatter Plot** | Shows the relationship and trendline between two numbers. |
| **Multiple Numeric Columns** | **Correlation Heatmap** | Shows how strongly different numbers are related. |
| **Single Numeric Column** | **Histogram + Box Plot** | Shows data spread, distribution, and outliers. |

---

## 📁 Project Structure

```text
automatic-chart-generator/
│
├── app.py              # Main application (Data Cleaning, Charting & Gradio Web UI)
├── requirements.txt    # Python libraries required
├── sample.csv          # Sample sales dataset for testing (400 rows x 11 columns)
├── .gitignore          # Git ignore file
├── LICENSE             # MIT License
└── README.md           # Project documentation
```

---

## 🚀 How to Run Locally

### 1. Prerequisites
Make sure you have **Python 3.10 or higher** installed on your computer.

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/automatic-chart-generator.git
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

### 5. Run the App
```bash
python app.py
```

Now open your web browser and go to:
```
http://127.0.0.1:7860
```
Drag and drop the included `sample.csv` file into the upload box to test the app!

---

## ☁️ Free Cloud Deployment (Render.com)

You can easily host this application online for free using [Render.com](https://render.com/):

1. Push your project code to your **GitHub repository**.
2. Go to [Render.com](https://render.com/) and sign up with GitHub.
3. Click on **New +** and select **Web Service**.
4. Connect your `automatic-chart-generator` repository.
5. Fill in the following settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python app.py`
   - **Plan:** `Free`
6. Click **Deploy Web Service**. Render will give you a free permanent link to share with anyone!

---

## 🛠️ Built With

- **[Python](https://www.python.org/)** - Core programming language
- **[Gradio](https://gradio.app/)** - Web interface and interactive components
- **[Pandas](https://pandas.pydata.org/)** - Data loading, cleaning, and statistics
- **[Plotly](https://plotly.com/)** - Interactive charts and visualizations
- **[NumPy](https://numpy.org/)** - Numerical calculations

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Designed and built with clean code and simple logic for easy data exploration.</sub>
</div>
