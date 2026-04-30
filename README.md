# Nokia Router Log Analyzer & MOP Generator

Welcome to the Nokia Router Toolkit. This application helps extract live SAP data, IP mappings, and Admin Down port statuses directly from Nokia `admin display configuration` terminal logs. 

Additionally, it features a full **Service Migration Engine** which cross-references an Excel Migration Plan against your raw router logs to dynamically generate accurate Deletion and Creation Command Line Scripts (MOPs).

---

## 🚀 How to Run on ANY Windows Computer

### Prerequisites
1. **Download and Install Python:**
   - Go to [python.org/downloads](https://www.python.org/downloads/) and download the latest Windows installer.
   - **⚠️ CRITICAL STEP:** When the installer opens, BEFORE you click Install, make sure you CHECK the box at the bottom that says **"Add Python to PATH"**. (If you miss this, terminal commands won't work!).
   - Click "Install Now".

### Installation
1. Extract this folder (`Nokia_Router_Tool`) anywhere on your computer (e.g., your Desktop).
2. Open the extracted folder.
3. **Open a Command Prompt inside the folder:**
   - Click on the file explorer path bar at the top of the folder window.
   - Delete the path, type `cmd`, and hit **Enter**. 
   - A black Terminal window will open directly inside your project folder.
4. **Install the Requirements:**
   - In the terminal, type the following command and hit Enter:
     ```cmd
     pip install -r requirements.txt
     ```
   - Let it download and install Streamlit, Pandas, and the Excel engines.

### Running the Website
1. In the exact same black Terminal window, type:
   ```cmd
   python -m streamlit run app.py
   ```
2. Your default web browser (Chrome, Edge, etc.) will automatically open up and launch the application!

---

### Project Files Overview
- `app.py`: The Main Web Interface (Frontend).
- `nokia_parser.py`: The Engine script containing all the data extraction and cross-referencing logic.
- `requirements.txt`: List of dependencies needed to handle Excel and Web UI.
- `README.txt`: This documentation file.
