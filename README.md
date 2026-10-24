# 🌊 FloodWatch Nepal

**AI-Assisted Flood Extent Mapping & Settlement Impact Assessment for the Nepal Terai**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36%2B-FF4B4B.svg)](https://streamlit.io/)
[![GeoPandas](https://img.shields.io/badge/GeoPandas-1.2%2B-green.svg)](https://geopandas.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

FloodWatch Nepal is a specialized disaster-management web application designed for rapid flood extent mapping and settlement exposure assessment across the flood-prone plains of the **Nepal Terai** (e.g., Koshi, Narayani, Rapti, and Babai river basins). 

Built for disaster managers, local municipalities, and humanitarian responders, the application visualizes flood inundation footprints, performs sub-meter metric spatial intersections against settlement and building footprints, and categorizes infrastructure exposure risk.

---

## 🏗️ Architecture & Project Structure

```text
FloodWatchNepal/
├── app.py                      # Main Streamlit dashboard & multi-page navigation
├── requirements.txt            # Python dependencies (GeoPandas, Folium, Plotly, etc.)
├── README.md                   # Complete documentation and Windows guide
├── .gitignore                  # Git ignore rules for Python, virtual environments, and OS
│
├── src/                        # Modular application components
│   ├── data_loader.py          # Vector loading, OGC validation, CRS handling & repair
│   ├── impact_assessment.py    # Spatial intersections, metric UTM area & exposure analysis
│   ├── map_visualization.py    # Folium interactive GIS map with custom styling & legends
│   └── flood_detection.py      # Sentinel-1 SAR GEE pipeline architecture & script generator
│
├── data/
│   └── demo/                   # Synthetic illustrative datasets for demonstration
│       ├── synthetic_flood_extent.geojson  # Riverine flood inundation corridor
│       ├── synthetic_settlements.geojson   # 14 settlement polygons & critical facilities
│       └── nepal_terai_districts.geojson   # Terai district boundaries (Sunsari / Saptari)
│
└── tests/
    └── test_impact_assessment.py # 10 unit & integration tests covering all geospatial logic
```

---

## 💻 Windows Setup & Installation Guide

Follow these step-by-step instructions to run FloodWatch Nepal on Windows:

### Step 1: Ensure Python is Installed
Make sure **Python 3.10 or newer** (tested on Python 3.12) is installed.
When installing Python from [python.org](https://www.python.org/downloads/), ensure you check:
> **☑️ Add python.exe to PATH**

Verify in PowerShell or Command Prompt:
```powershell
python --version
```

### Step 2: Open Terminal in the Project Directory
Open **PowerShell** or **Command Prompt** and navigate to the project directory:
```powershell
cd c:\Users\anmol\OneDrive\Attachments\Desktop\FloodWatchNepal
```

### Step 3: Create a Python Virtual Environment
A virtual environment keeps project dependencies isolated and clean:
```powershell
python -m venv .venv
```

### Step 4: Activate the Virtual Environment
In PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell blocks script execution, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once, then re-run the activate command).*

Or in standard Windows Command Prompt (`cmd.exe`):
```cmd
.\.venv\Scripts\activate.bat
```

You will see `(.venv)` in your terminal prompt.

### Step 5: Install Required Dependencies
Install the geospatial and web dashboard packages:
```powershell
pip install -r requirements.txt
```

### Step 6: Launch the Application
Run the Streamlit application:
```powershell
streamlit run app.py
```

Streamlit will compile the application and open your default browser automatically at:
```text
http://localhost:8501
```

---

## 🚀 How to Use the Application

### 1. Instant Demonstration Mode
1. Click the navy sidebar on the left.
2. Click the prominent button: **"🚀 Load Demonstration Scenario"**.
3. The application will instantly load the synthetic Terai scenario (Koshi River basin across Sunsari and Saptari districts):
   - **Flooded Extent**: 542.40 km² calculated from synthetic inundation geometries.
   - **Settlement Evaluation**: 14 features (7 settlement polygons and 7 critical facility points including schools, clinics, and evacuation shelters).
   - **Calculated Exposure**: 9 features intersect the inundation zone (52.31% overall exposure rate).
   - **Interactive Folium Map**: Blue/cyan flood inundation layer, red/orange highlighted exposed features, and teal unexposed features.
4. Download the resulting enriched GeoJSON, flood extent GeoJSON, or CSV impact summary table.

> **Disclaimer**: All synthetic demo data is clearly watermarked and labeled as illustrative demonstration data—not an actual satellite observation or confirmed ground damage.

### 2. Uploading Custom GeoJSON Datasets
1. Navigate to **"📤 Data Upload & Inspection"** in the sidebar.
2. Upload your own **Flood Extent GeoJSON** (polygons representing inundated areas).
3. Upload your **Settlement / Building GeoJSON** (polygons representing village footprints or points representing buildings).
4. The built-in validator will automatically:
   - Check and repair self-intersecting or invalid geometries (`shapely.validation.make_valid`).
   - Standardize CRS to `EPSG:4326` (WGS84) for mapping.
   - Auto-detect the optimal metric projection for area calculations.
5. Return to the **"📊 Dashboard & Impact Map"** to view real-time metrics and overlay maps.

### 3. Satellite SAR Architecture (Sentinel-1 & Google Earth Engine)
1. Navigate to **"🛰️ Satellite Architecture (SAR)"**.
2. Inspect the **Google Earth Engine (GEE)** connection status.
3. Review the complete 10-step scientific methodology for C-band radar flood detection.
4. Use the interactive parameter controls (select district, pre-flood baseline dates, post-flood event dates, and dB difference threshold).
5. Generate and copy ready-to-run Google Earth Engine Python code to execute on Google Cloud or Earth Engine Code Editor.

---

## 📐 Scientific & Geospatial Methodology

### Why Not Calculate Area in Degrees?
Standard WGS84 coordinates (`EPSG:4326`) are spherical angular degrees. Calculating polygon areas in degree units produces massive distortion. FloodWatch Nepal automatically reprojects datasets into the correct **Universal Transverse Mercator (UTM)** zone for Nepal:
- **Western Nepal (78°E to 84°E)**: UTM Zone 44N (`EPSG:32644`)
- **Central & Eastern Nepal (84°E to 90°E)**: UTM Zone 45N (`EPSG:32645`)

This ensures millimetric metric precision for area ($m^2$, $km^2$, $ha$) and spatial intersections.

### Exposure vs Confirmed Damage
FloodWatch Nepal strictly adheres to humanitarian GIS standards:
- **Potentially Exposed**: Indicates that a settlement polygon or building point falls within the spatial boundaries of the detected water footprint.
- **Why it is NOT "Confirmed Damage"**:
  1. **Plinth Height**: Many Terai homes are constructed on elevated earth mounds or stilts.
  2. **Inundation Depth**: A 10 cm water depth disrupts mobility but rarely collapses structures, whereas 2-meter fast-flowing torrents cause destruction.
  3. **Construction Material**: Reinforced concrete frames withstand inundation far better than mud-thatch or unreinforced masonry.
  
Ground truthing and multi-temporal hazard modeling remain essential for damage verification.

---

## 🧪 Running the Test Suite

FloodWatch Nepal includes a full test suite covering spatial intersections, area calculation, empty/invalid input handling, GeoJSON export, and map compilation:

To run all tests inside the virtual environment:
```powershell
pytest -v tests
```

Expected output:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.5, pytest-9.1.1
collected 10 items

tests/test_impact_assessment.py::test_flood_extent_area_calculation PASSED          [ 10%]
tests/test_impact_assessment.py::test_settlement_polygon_spatial_intersection PASSED [ 20%]
tests/test_impact_assessment.py::test_settlement_point_spatial_intersection PASSED   [ 30%]
tests/test_impact_assessment.py::test_empty_flood_dataset_handling PASSED           [ 40%]
tests/test_impact_assessment.py::test_empty_settlement_dataset_handling PASSED      [ 50%]
tests/test_impact_assessment.py::test_invalid_geometry_repair_and_validation PASSED  [ 60%]
tests/test_impact_assessment.py::test_missing_crs_defaulting PASSED               [ 70%]
tests/test_impact_assessment.py::test_geojson_export PASSED                       [ 80%]
tests/test_impact_assessment.py::test_satellite_architecture_graceful_status PASSED  [ 90%]
tests/test_impact_assessment.py::test_demo_scenario_data_and_map_rendering PASSED  [100%]

============================= 10 passed in 1.71s ==============================
```

---

## 🛰️ Open Data Sources

1. **Copernicus Sentinel-1 SAR**:
   - European Space Agency (ESA) Copernicus Open Access Hub / Data Space: [https://dataspace.copernicus.eu/](https://dataspace.copernicus.eu/)
   - *Limitation*: Revisit cycle over Nepal is 6 to 12 days; not a real-time live video feed.
2. **OpenStreetMap Nepal**:
   - Building footprints and settlement points curated by Kathmandu Living Labs (KLL): [https://download.geofabrik.de/asia/nepal.html](https://download.geofabrik.de/asia/nepal.html)
3. **Google Open Buildings V3**:
   - Machine-learning derived building polygons across South Asia: [https://sites.research.google/open-buildings/](https://sites.research.google/open-buildings/)
4. **UN OCHA HDX Nepal**:
   - Administrative boundary shapes, health facilities, and school locations: [https://data.humdata.org/group/npl](https://data.humdata.org/group/npl)
5. **JRC Global Surface Water**:
   - 38-year global surface water seasonality dataset to mask permanent rivers: [https://global-surface-water.appspot.com/](https://global-surface-water.appspot.com/)

---

## ⚖️ Known Limitations & Future Roadmap

- **Satellite Latency**: Sentinel-1 SAR is subject to orbital revisit cycles (typically 6–12 days). Inundation mapping represents the satellite overpass timestamp.
- **Urban Layover & Dense Canopy**: Radar backscatter in high-density urban areas or dense sal forests can experience radar shadow or double-bounce backscatter.
- **Future Roadmap**:
  - Integration with authenticated Google Earth Engine service account for automated daily ingest.
  - Integration with GloFAS (Global Flood Awareness System) and Nepal Department of Hydrology and Meteorology (DHM) river gauge telemetry.
  - Machine learning hydrodynamic depth estimation using 12.5m ALOS PALSAR DEM.

---

## 📜 License
Developed for humanitarian, academic, and disaster risk reduction applications under the **MIT License**.
