"""
FloodWatch Nepal
AI-Assisted Flood Extent Mapping & Settlement Impact Assessment for the Nepal Terai

Tech Stack: Streamlit, GeoPandas, Shapely, Folium, streamlit-folium, Pandas, Plotly
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.data_loader import (
    export_gdf_to_geojson_string,
    inspect_vector_dataset,
    load_vector_dataset,
)
from src.flood_detection import Sentinel1SARPipeline, get_satellite_sensor_comparison
from src.impact_assessment import (
    DISCLAIMER_TEXT,
    assess_settlement_impact,
    calculate_flood_extent_metrics,
    get_optimal_nepal_utm_crs,
)
from src.map_visualization import create_flood_map

# ------------------------------------------------------------------------------
# Page Configuration & CSS Styling
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="FloodWatch Nepal",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern disaster-management dashboard:
# Navy-blue sidebar, clean light-gray background, cyan/blue flood & orange/red risk accents
st.markdown(
    """
    <style>
    /* Global styles */
    .stApp {
        background-color: #f8f9fa;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0b1a30;
        color: #f8f9fa;
        border-right: 1px solid #1e3a5f;
    }
    section[data-testid="stSidebar"] .stMarkdown h1, 
    section[data-testid="stSidebar"] .stMarkdown h2, 
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #e0e6ed !important;
    }
    section[data-testid="stSidebar"] label {
        color: #c9d6df !important;
    }
    section[data-testid="stSidebar"] p {
        color: #b0c4de !important;
    }
    
    /* Header Card */
    .dashboard-header {
        background: linear-gradient(135deg, #0b1a30 0%, #173254 100%);
        color: #ffffff;
        padding: 24px 28px;
        border-radius: 12px;
        margin-bottom: 24px;
        box-shadow: 0 4px 16px rgba(11, 26, 48, 0.15);
        border-left: 6px solid #00b4d8;
    }
    .dashboard-header h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #ffffff !important;
    }
    .dashboard-header p {
        margin: 6px 0 0 0;
        font-size: 15px;
        color: #90e0ef;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #ffffff;
        padding: 16px 20px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #0077b6;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }
    .metric-card.danger {
        border-left-color: #e63946;
    }
    .metric-card.warning {
        border-left-color: #f77f00;
    }
    .metric-card.info {
        border-left-color: #00b4d8;
    }
    .metric-card.success {
        border-left-color: #2a9d8f;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #64748b;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
    }

    /* Badges */
    .badge-exposed {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
        border: 1px solid #fecaca;
    }
    .badge-safe {
        background-color: #d1fae5;
        color: #065f46;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
        border: 1px solid #a7f3d0;
    }
    .badge-demo {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
        border: 1px solid #fde68a;
    }

    /* Notice banner */
    .notice-box {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        border-left: 4px solid #2563eb;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        color: #1e40af;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# Session State Initialization
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

if "flood_gdf" not in st.session_state:
    st.session_state.flood_gdf = None

if "settlement_gdf" not in st.session_state:
    st.session_state.settlement_gdf = None

if "study_area_gdf" not in st.session_state:
    st.session_state.study_area_gdf = None

if "is_demo_mode" not in st.session_state:
    st.session_state.is_demo_mode = False

if "demo_source_name" not in st.session_state:
    st.session_state.demo_source_name = "None"


def load_demonstration_scenario():
    """Loads pre-configured synthetic scenario for Nepal Terai (Sunsari / Saptari)."""
    demo_dir = BASE_DIR / "data" / "demo"
    flood_path = demo_dir / "synthetic_flood_extent.geojson"
    settle_path = demo_dir / "synthetic_settlements.geojson"
    study_path = demo_dir / "nepal_terai_districts.geojson"

    if not flood_path.exists() or not settle_path.exists():
        st.error("Demo dataset files missing from data/demo directory.")
        return

    flood_gdf, _ = load_vector_dataset(flood_path)
    settle_gdf, _ = load_vector_dataset(settle_path)
    study_gdf, _ = load_vector_dataset(study_path) if study_path.exists() else (None, None)

    st.session_state.flood_gdf = flood_gdf
    st.session_state.settlement_gdf = settle_gdf
    st.session_state.study_area_gdf = study_gdf
    st.session_state.is_demo_mode = True
    st.session_state.demo_source_name = "Koshi Basin (Sunsari / Saptari) - Synthetic Demo"


# ------------------------------------------------------------------------------
# Sidebar Navigation & Controls
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌊 FloodWatch Nepal")
    st.caption("Rapid Flood Mapping & Exposure Assessment")
    st.markdown("---")

    # Main Navigation
    app_mode = st.radio(
        "Navigation",
        [
            "📊 Dashboard & Impact Map",
            "📤 Data Upload & Inspection",
            "🛰️ Satellite Architecture (SAR)",
            "📖 Data Sources & Methodology",
        ],
        index=0,
    )

    st.markdown("---")
    st.markdown("### ⚡ Quick Scenario")

    # Demo Button
    if st.button("🚀 Load Demonstration Scenario", use_container_width=True, type="primary"):
        load_demonstration_scenario()
        st.success("Loaded synthetic Terai scenario!")
        st.rerun()

    if st.session_state.is_demo_mode:
        st.markdown(
            """
            <div class="badge-demo">
                ⚠️ DEMO MODE ACTIVE<br>
                <small>Synthetic illustrative geometries</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 📍 Study Area: Nepal Terai")
    st.info(
        "**Geographic Focus:**\n"
        "- Elevation: Lowland floodplains (60m - 250m)\n"
        "- River Basins: Koshi, Narayani, Rapti, Babai\n"
        "- Metric CRS: Nepal UTM Zone 44N / 45N"
    )

    if st.button("🧹 Reset / Clear Datasets", use_container_width=True):
        st.session_state.flood_gdf = None
        st.session_state.settlement_gdf = None
        st.session_state.study_area_gdf = None
        st.session_state.is_demo_mode = False
        st.session_state.demo_source_name = "None"
        st.rerun()

    st.markdown("---")
    st.caption("FloodWatch Nepal v1.0 • Hackathon Edition")


# ------------------------------------------------------------------------------
# Helper for Banner Header
# ------------------------------------------------------------------------------
def render_header(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="dashboard-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------------------
# PAGE 1: DASHBOARD & INTERACTIVE IMPACT MAP
# ------------------------------------------------------------------------------
if app_mode == "📊 Dashboard & Impact Map":
    render_header(
        "FloodWatch Nepal",
        "AI-Assisted Flood Extent Mapping & Settlement Impact Assessment • Nepal Terai",
    )

    # Demo Mode Warning Banner
    if st.session_state.is_demo_mode:
        st.warning(
            "🧪 **DEMONSTRATION SCENARIO LOADED**: The flood extent polygons and settlement features below are "
            "synthetic and illustrative for system demonstration. They do NOT represent real satellite observations "
            "or confirmed Nepal ground damage.",
            icon="⚠️",
        )

    # Check if data is loaded
    has_flood = st.session_state.flood_gdf is not None and len(st.session_state.flood_gdf) > 0
    has_settle = st.session_state.settlement_gdf is not None and len(st.session_state.settlement_gdf) > 0

    if not has_flood and not has_settle:
        st.markdown(
            """
            <div class="notice-box">
                <strong>No geospatial datasets loaded.</strong><br>
                Please click <strong>"Load Demonstration Scenario"</strong> in the sidebar to view an instant illustrative scenario,
                or go to <strong>"Data Upload & Inspection"</strong> to supply your own GeoJSON layers.
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if st.button("🚀 Load Demonstration Scenario Now", type="primary", use_container_width=True):
                load_demonstration_scenario()
                st.rerun()

    else:
        # Perform live impact calculation
        with st.spinner("Calculating spatial intersections and metric projections..."):
            enriched_settlements, metrics = assess_settlement_impact(
                st.session_state.flood_gdf,
                st.session_state.settlement_gdf,
            )

        # ---------------------------------------------------------
        # KPI Metric Cards (Calculated from actual data)
        # ---------------------------------------------------------
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            flood_km2 = metrics.get("flood_area_km2", 0.0)
            flood_ha = metrics.get("flood_area_ha", 0.0)
            poly_count = metrics.get("flood_polygon_count", 0) if "flood_polygon_count" in metrics else len(st.session_state.flood_gdf) if has_flood else 0
            st.markdown(
                f"""
                <div class="metric-card info">
                    <div class="metric-label">Flooded Extent Area</div>
                    <div class="metric-value">{flood_km2:,.2f} <span style="font-size: 16px;">km²</span></div>
                    <div class="metric-sub">{flood_ha:,.1f} ha • {poly_count} flood polygon(s)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            total_settlements = metrics.get("total_settlements", 0)
            poly_feats = metrics.get("polygon_features", 0)
            pt_feats = metrics.get("point_features", 0)
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Settlement Features</div>
                    <div class="metric-value">{total_settlements:,}</div>
                    <div class="metric-sub">{poly_feats} polygon footprints • {pt_feats} points</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:
            exposed_count = metrics.get("exposed_count", 0)
            exp_pct = metrics.get("settlement_exposure_pct", 0.0)
            st.markdown(
                f"""
                <div class="metric-card danger">
                    <div class="metric-label">Potentially Exposed Features</div>
                    <div class="metric-value">{exposed_count:,}</div>
                    <div class="metric-sub">{exp_pct:.1f}% of evaluated features exposed</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col4:
            exp_polys = metrics.get("exposed_polygons", 0)
            exp_pts = metrics.get("exposed_points", 0)
            crs_name = metrics.get("metric_crs", "EPSG:32645")
            st.markdown(
                f"""
                <div class="metric-card warning">
                    <div class="metric-label">Exposed Polygons / Points</div>
                    <div class="metric-value">{exp_polys} / {exp_pts}</div>
                    <div class="metric-sub">Calculated via {crs_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Scientific Disclaimer Box
        st.markdown(
            f"""
            <div class="notice-box">
                ℹ️ <strong>Scientific Disclaimer:</strong> {DISCLAIMER_TEXT}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------------------------------------------
        # Interactive Folium Map
        # ---------------------------------------------------------
        st.markdown("### 🗺️ Geospatial Impact Map")
        st.caption("Layer control in top-right. Click or hover on features for localized impact statistics.")

        fmap = create_flood_map(
            flood_gdf=st.session_state.flood_gdf,
            settlement_gdf=enriched_settlements,
            study_area_gdf=st.session_state.study_area_gdf,
            show_legend=True,
        )

        # Render Folium map in Streamlit
        st_folium(fmap, use_container_width=True, height=520, returned_objects=[])

        # ---------------------------------------------------------
        # Plotly Statistical Visualizations
        # ---------------------------------------------------------
        st.markdown("### 📈 Exposure Analytics")
        tab_charts, tab_table = st.tabs(["📊 Distribution Charts", "📋 Detailed Feature Table"])

        with tab_charts:
            c1, c2 = st.columns(2)

            with c1:
                # Risk level donut chart
                if "risk_level" in enriched_settlements.columns and len(enriched_settlements) > 0:
                    risk_counts = enriched_settlements["risk_level"].value_counts().reset_index()
                    risk_counts.columns = ["Risk Level", "Count"]

                    # Explicit risk color map
                    color_map = {
                        "High Exposure": "#e63946",
                        "Moderate Exposure": "#f77f00",
                        "Low Exposure": "#ffb703",
                        "None": "#adb5bd",
                    }

                    fig_risk = px.pie(
                        risk_counts,
                        names="Risk Level",
                        values="Count",
                        title="Settlement Features by Flood Exposure Risk Level",
                        color="Risk Level",
                        color_discrete_map=color_map,
                        hole=0.45,
                    )
                    fig_risk.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=320)
                    st.plotly_chart(fig_risk, use_container_width=True)
                else:
                    st.info("No risk classification data to chart.")

            with c2:
                # Exposure by feature type
                if "feature_type" in enriched_settlements.columns and len(enriched_settlements) > 0:
                    type_df = (
                        enriched_settlements.groupby(["feature_type", "exposure_status"])
                        .size()
                        .reset_index(name="Count")
                    )

                    fig_type = px.bar(
                        type_df,
                        x="feature_type",
                        y="Count",
                        color="exposure_status",
                        title="Exposure Status by Feature Type",
                        barmode="group",
                        color_discrete_map={
                            "Potentially Exposed": "#e63946",
                            "Not Exposed": "#457b9d",
                        },
                    )
                    fig_type.update_layout(
                        margin=dict(l=20, r=20, t=40, b=20),
                        height=320,
                        xaxis_title="Feature Category",
                        yaxis_title="Feature Count",
                    )
                    st.plotly_chart(fig_type, use_container_width=True)
                else:
                    st.info("No feature type attributes found.")

        with tab_table:
            # Filter options
            f_col1, f_col2 = st.columns([1, 2])
            with f_col1:
                filter_status = st.selectbox(
                    "Filter by Exposure Status",
                    ["All Features", "Potentially Exposed Only", "Safe / Unexposed Only"],
                )
            with f_col2:
                search_term = st.text_input("🔍 Search by Settlement Name or District", "")

            # Filter data
            display_df = enriched_settlements.copy()
            if filter_status == "Potentially Exposed Only":
                display_df = display_df[display_df["is_exposed"] == True]
            elif filter_status == "Safe / Unexposed Only":
                display_df = display_df[display_df["is_exposed"] == False]

            if search_term.strip():
                cols_to_search = [c for c in ["name", "settlement_name", "district", "municipality"] if c in display_df.columns]
                if cols_to_search:
                    mask = False
                    for c in cols_to_search:
                        mask = mask | display_df[c].astype(str).str.contains(search_term, case=False, na=False)
                    display_df = display_df[mask]

            # Presentable table columns
            table_cols = [
                c for c in [
                    "name", "settlement_name", "district", "municipality", "feature_type",
                    "exposure_status", "exposure_percentage", "flooded_area_ha", "risk_level"
                ] if c in display_df.columns
            ]

            if len(display_df) > 0 and table_cols:
                st.dataframe(
                    display_df[table_cols],
                    use_container_width=True,
                    height=280,
                )
            else:
                st.info("No features matching current filter criteria.")

        # ---------------------------------------------------------
        # Download Resulting GeoJSON and CSV
        # ---------------------------------------------------------
        st.markdown("### 📥 Export Assessment Results")
        col_d1, col_d2, col_d3 = st.columns(3)

        with col_d1:
            settle_geojson_str = export_gdf_to_geojson_string(enriched_settlements)
            st.download_button(
                label="📥 Download Enriched Settlements (GeoJSON)",
                data=settle_geojson_str,
                file_name="floodwatch_nepal_exposed_settlements.geojson",
                mime="application/geo+json",
                use_container_width=True,
            )

        with col_d2:
            if has_flood:
                flood_geojson_str = export_gdf_to_geojson_string(st.session_state.flood_gdf)
                st.download_button(
                    label="📥 Download Flood Extent (GeoJSON)",
                    data=flood_geojson_str,
                    file_name="floodwatch_nepal_flood_extent.geojson",
                    mime="application/geo+json",
                    use_container_width=True,
                )
            else:
                st.button("📥 Download Flood Extent (No data)", disabled=True, use_container_width=True)

        with col_d3:
            # CSV summary
            csv_buffer = io.StringIO()
            cols_csv = [c for c in enriched_settlements.columns if c != "geometry"]
            enriched_settlements[cols_csv].to_csv(csv_buffer, index=False)
            st.download_button(
                label="📊 Download Impact Summary (CSV)",
                data=csv_buffer.getvalue(),
                file_name="floodwatch_nepal_impact_report.csv",
                mime="text/csv",
                use_container_width=True,
            )


# ------------------------------------------------------------------------------
# PAGE 2: DATA UPLOAD & GEOSPATIAL VALIDATION
# ------------------------------------------------------------------------------
elif app_mode == "📤 Data Upload & Inspection":
    render_header(
        "Data Upload & Geospatial Validation",
        "Upload Flood Extent and Settlement/Building Layers for Custom Analysis",
    )

    st.markdown(
        """
        Upload your own vector GeoJSON files representing:
        1. **Flood Extent**: Inundation polygons extracted from Sentinel-1 SAR, Sentinel-2, or hydrological modeling.
        2. **Settlements / Buildings**: Building footprints or settlement point coordinates (e.g. from OpenStreetMap or Google Open Buildings).
        """
    )

    u_col1, u_col2 = st.columns(2)

    with u_col1:
        st.markdown("#### 1. Flood Inundation Extent (GeoJSON)")
        uploaded_flood = st.file_uploader(
            "Upload Flood GeoJSON",
            type=["geojson", "json"],
            key="flood_uploader",
            help="Polygons representing flooded surface areas in WGS84 or UTM projection.",
        )
        if uploaded_flood is not None:
            try:
                gdf_f, warn_f = load_vector_dataset(uploaded_flood)
                st.session_state.flood_gdf = gdf_f
                st.session_state.is_demo_mode = False
                st.success(f"Successfully loaded flood layer ({len(gdf_f)} features).")
                if warn_f:
                    st.warning(warn_f)

                meta_f = inspect_vector_dataset(gdf_f)
                st.json(meta_f)
            except Exception as e:
                st.error(f"Error parsing flood file: {str(e)}")

    with u_col2:
        st.markdown("#### 2. Settlement / Building Footprints (GeoJSON)")
        uploaded_settle = st.file_uploader(
            "Upload Settlements GeoJSON",
            type=["geojson", "json"],
            key="settle_uploader",
            help="Settlement polygons or building points in WGS84 or UTM projection.",
        )
        if uploaded_settle is not None:
            try:
                gdf_s, warn_s = load_vector_dataset(uploaded_settle)
                st.session_state.settlement_gdf = gdf_s
                st.session_state.is_demo_mode = False
                st.success(f"Successfully loaded settlement layer ({len(gdf_s)} features).")
                if warn_s:
                    st.warning(warn_s)

                meta_s = inspect_vector_dataset(gdf_s)
                st.json(meta_s)
            except Exception as e:
                st.error(f"Error parsing settlement file: {str(e)}")

    st.markdown("---")
    st.markdown("#### 3. Optional Flood Raster Upload (GeoTIFF)")
    uploaded_raster = st.file_uploader(
        "Upload Flood Raster (Optional)",
        type=["tif", "tiff"],
        key="raster_uploader",
        help="Optional satellite raster file. (Note: In standard vector workflow, vectorized GeoJSON is used for high-speed spatial intersections).",
    )
    if uploaded_raster is not None:
        st.info(
            f"Raster file **{uploaded_raster.name}** ({uploaded_raster.size / 1024:.1f} KB) uploaded. "
            "For optimal browser performance, polygonize your flood raster using GDAL `gdal_polygonize.py` "
            "or the built-in Sentinel-1 vectorizer before running spatial exposure overlays."
        )

    st.markdown("---")
    st.markdown("### 🔍 Geospatial Validation Protocol")
    st.markdown(
        """
        FloodWatch Nepal automatically enforces:
        - **OGC SFS Geometry Validity**: Auto-detects and repairs self-intersections (bowties) via `shapely.validation.make_valid()`.
        - **CRS Compatibility**: Verifies Coordinate Reference Systems, defaulting safely to EPSG:4326 (WGS84).
        - **Metric Projection Auto-Detection**: Dynamically assigns Nepal UTM Zone 44N (Western Nepal) or UTM Zone 45N (Central & Eastern Nepal) for millimetric area and distance accuracy.
        - **Empty Layer Protection**: Safely handles zero-feature files or missing geometry attributes without crashing.
        """
    )


# ------------------------------------------------------------------------------
# PAGE 3: SATELLITE ARCHITECTURE (SENTINEL-1 SAR & EARTH ENGINE)
# ------------------------------------------------------------------------------
elif app_mode == "🛰️ Satellite Architecture (SAR)":
    render_header(
        "Sentinel-1 SAR Satellite Architecture",
        "Synthetic Aperture Radar Inundation Processing Pipeline for the Nepal Terai",
    )

    pipeline = Sentinel1SARPipeline()
    status = pipeline.status

    # GEE Status Display
    st.markdown("### 🔌 Earth Engine Connectivity Status")
    if status.is_authenticated:
        st.success(f"✅ {status.status_message}")
    else:
        st.warning(
            f"⚠️ **Satellite Cloud Engine Status:** {status.status_message}\n\n"
            "**Operational Transparency Note:** Satellite processing through Google Earth Engine is designed and structured modularly, "
            "but requires your own authenticated GCP credentials (`earthengine authenticate`). "
            "The rest of FloodWatch Nepal operates with 100% functionality using uploaded GeoJSON files or the Synthetic Demo Scenario.",
            icon="🔒",
        )

    st.markdown("---")
    st.markdown("### 🛰️ The Sentinel-1 SAR Scientific Methodology")
    st.markdown(
        """
        Why Synthetic Aperture Radar (SAR) for Nepal?
        During the South Asian Summer Monsoon (June–September), **optical satellites (Sentinel-2, Landsat) are blinded by dense 90–100% cloud cover**.
        Sentinel-1 operates in the **C-band microwave spectrum (5.405 GHz)**, allowing it to penetrate through clouds, rain, and nighttime darkness.
        """
    )

    # 10 Step Pipeline Breakdown
    with st.expander("🔬 View Step-by-Step 10-Stage SAR Processing Workflow", expanded=True):
        st.markdown(
            """
            1. **Sensor Selection**: Sentinel-1 Level-1 Ground Range Detected (GRD) in Interferometric Wide (IW) swath mode.
            2. **Polarization Pairing**: Dual polarization (VV + VH). VV polarization provides the highest contrast between calm flood water and dry terrain.
            3. **Baseline Composite Generation**: Filter pre-flood acquisitions (30-day window) and compute median radar backscatter $\\sigma^0_{pre}$.
            4. **Event Acquisition**: Select post-flood SAR scene taken during or immediately after peak river cresting $\\sigma^0_{post}$.
            5. **Radiometric Calibration & Speckle Filtering**: Convert to backscatter decibels (dB) and apply a 5x5 focal filter to eliminate salt-and-pepper radar speckle noise.
            6. **Difference Log-Ratio**: Calculate $\\Delta \\sigma^0 = \\sigma^0_{post} - \\sigma^0_{pre}$. Specular reflection off smooth flood water causes a sharp drop in backscatter.
            7. **Thresholding**: Apply change threshold (typically $-3.2\\text{ dB}$ or absolute $<-15\\text{ dB}$) to isolate newly inundated pixels.
            8. **Topographic Slope Masking**: In Nepal, steep mountain slopes cast radar shadow resembling water. We apply **NASADEM / SRTM 30m** to mask all slopes $> 5\\%$.
            9. **Permanent Water Masking**: Mask out perennial rivers and lakes using the **JRC Global Surface Water** 38-year seasonality record to isolate *flood* inundation from normal river courses.
            10. **Vectorization**: Convert 10m binary raster water mask into GeoJSON multi-polygons for ingestion into FloodWatch Nepal.
            """
        )

    st.markdown("---")
    st.markdown("### 🛠️ Interactive GEE Script Generator")
    st.caption("Generate copy-pasteable Python code to execute on Google Earth Engine Code Editor or local notebooks.")

    c_g1, c_g2, c_g3 = st.columns(3)
    with c_g1:
        district_target = st.selectbox(
            "Nepal Terai District",
            ["Sunsari", "Saptari", "Siraha", "Dhanusha", "Rautahat", "Bardiya", "Kailali"],
        )
    with c_g2:
        pre_dates = st.date_input("Pre-Flood Baseline Window", [date(2024, 6, 1), date(2024, 6, 30)])
    with c_g3:
        post_dates = st.date_input("Post-Flood Event Window", [date(2024, 7, 8), date(2024, 7, 15)])

    threshold_slider = st.slider(
        "Radar Backscatter Difference Threshold (dB)",
        min_value=-6.0,
        max_value=-1.5,
        value=-3.2,
        step=0.1,
        help="Lower values are more conservative; -3.2 dB is standard for monsoonal Terai plains.",
    )

    if isinstance(pre_dates, (list, tuple)) and len(pre_dates) == 2 and isinstance(post_dates, (list, tuple)) and len(post_dates) == 2:
        gee_code = pipeline.generate_gee_python_script(
            district_name=district_target,
            pre_start=str(pre_dates[0]),
            pre_end=str(pre_dates[1]),
            post_start=str(post_dates[0]),
            post_end=str(post_dates[1]),
            threshold_db=threshold_slider,
        )
        st.code(gee_code, language="python")

    st.markdown("---")
    st.markdown("### 📊 Sensor Modality Comparison for Nepal Floods")
    sensors = get_satellite_sensor_comparison()
    st.table(pd.DataFrame(sensors))


# ------------------------------------------------------------------------------
# PAGE 4: DATA SOURCES & METHODOLOGY
# ------------------------------------------------------------------------------
elif app_mode == "📖 Data Sources & Methodology":
    render_header(
        "Data Sources & Scientific Documentation",
        "Authoritative Open Geospatial Datasets & Exposure Assessment Methodology",
    )

    st.markdown(
        """
        ### 🌐 Primary Geospatial Data Sources
        
        #### 1. Copernicus Sentinel-1 Synthetic Aperture Radar (SAR)
        - **Source**: European Space Agency (ESA) Copernicus Programme
        - **Link**: [https://dataspace.copernicus.eu/](https://dataspace.copernicus.eu/)
        - **Characteristics**: C-band (5.405 GHz) radar, 10m spatial resolution, 6-12 day revisit orbit.
        - **Operational Availability**: Satellite radar is **NOT a real-time live video stream**. Orbits pass over Nepal at specific intervals. Data becomes available 2 to 4 hours post-pass.
        
        #### 2. Settlement & Building Footprints
        - **OpenStreetMap (OSM) Nepal**: Curated by the Kathmandu Living Labs (KLL) and global OSM community.
          - Link: [https://download.geofabrik.de/asia/nepal.html](https://download.geofabrik.de/asia/nepal.html)
        - **Google Open Buildings V3**: High-resolution building polygons derived from AI segmentation of satellite imagery.
          - Link: [https://sites.research.google/open-buildings/](https://sites.research.google/open-buildings/)
        
        #### 3. Administrative Boundaries & Terai Baseline Data
        - **Survey Department of Nepal**: Official administrative boundaries (Provinces, Districts, Municipalities, Wards).
        - **UN OCHA Humanitarian Data Exchange (HDX) Nepal**:
          - Link: [https://data.humdata.org/group/npl](https://data.humdata.org/group/npl)
        - **JRC Global Surface Water (GSW)**: 38-year global surface water seasonality mapping to distinguish flood water from perennial wetlands.
          - Link: [https://global-surface-water.appspot.com/](https://global-surface-water.appspot.com/)
        
        ---
        ### 📐 Mathematical & Geospatial Methodology
        
        #### 1. Metric Projection for Accurate Area Computations
        Standard geographic coordinates (WGS84, `EPSG:4326`) express positions in angular degrees ($^{\circ}$).
        Calculating area directly on angular degrees causes severe latitude distortion.
        FloodWatch Nepal dynamically reprojects coordinates to standard **Universal Transverse Mercator (UTM)** metric systems:
        - Longitude $< 84.0^{\circ}\text{E}$: **WGS 84 / UTM Zone 44N (`EPSG:32644`)**
        - Longitude $\ge 84.0^{\circ}\text{E}$: **WGS 84 / UTM Zone 45N (`EPSG:32645`)**
        
        Flooded footprint area:
        $$\text{Area}_{\text{km}^2} = \frac{\text{Area}(\bigcup_{i=1}^n P_i)}{1,000,000}$$
        where $\bigcup P_i$ is the geometric union (dissolve) of all overlapping flood polygons to prevent duplicate counting.
        
        #### 2. Exposure Percentage Calculation
        For each settlement polygon $S_j$:
        $$\text{Exposure } \% = \min\left(100.0, \frac{\text{Area}(S_j \cap \text{Flood})}{\text{Area}(S_j)} \times 100\right)$$
        
        #### 3. Critical Terminology: Exposure vs Confirmed Damage
        - **Potentially Exposed**: A spatial intersection indicates that water occupies the horizontal footprint of a settlement or building.
        - **Why this does NOT equal confirmed damage**:
          - Building plinth elevations (e.g. houses on raised earth mounds or stilt structures common in Terai villages).
          - Multi-story masonry versus temporary thatch construction.
          - Water depth (a 10cm ankle-deep inundation versus a 2-meter destructive torrent).
        """
    )
