"""
Data Loader & Geospatial Validation Module
FloodWatch Nepal
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from shapely.validation import make_valid


def load_vector_dataset(
    source: Union[str, Path, BinaryIO, bytes, dict],
    default_crs: str = "EPSG:4326",
    auto_repair: bool = True,
) -> Tuple[Optional[gpd.GeoDataFrame], Optional[str]]:
    """
    Loads and validates a vector dataset (GeoJSON/Shapefile).

    Args:
        source: File path, file-like object (e.g. Streamlit UploadedFile), raw bytes, or dict.
        default_crs: CRS to assume if dataset has no CRS specified (default 'EPSG:4326').
        auto_repair: Whether to automatically repair invalid geometries using make_valid.

    Returns:
        Tuple of (GeoDataFrame or None, warning_message or None).
    """
    warning_msg = None

    try:
        # Load from various source types
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.exists():
                raise FileNotFoundError(f"File not found: {source}")
            if p.stat().st_size == 0:
                raise ValueError("Uploaded file is empty (0 bytes).")
            gdf = gpd.read_file(p)

        elif isinstance(source, dict):
            gdf = gpd.GeoDataFrame.from_features(source.get("features", []), crs=default_crs)

        elif isinstance(source, bytes):
            if len(source) == 0:
                raise ValueError("Uploaded file payload is empty.")
            json_data = json.loads(source.decode("utf-8"))
            gdf = gpd.GeoDataFrame.from_features(json_data.get("features", []), crs=default_crs)

        else:
            # File-like object (e.g. Streamlit UploadedFile)
            # Try reading directly with geopandas; fallback to json.load
            try:
                gdf = gpd.read_file(source)
            except Exception:
                # Reset stream pointer and try parsing as JSON GeoDataFrame
                if hasattr(source, "seek"):
                    source.seek(0)
                raw_bytes = source.read()
                if not raw_bytes:
                    raise ValueError("Uploaded file stream is empty.")
                if isinstance(raw_bytes, bytes):
                    raw_str = raw_bytes.decode("utf-8")
                else:
                    raw_str = raw_bytes
                json_data = json.loads(raw_str)
                features = json_data.get("features", [])
                if not features:
                    raise ValueError("GeoJSON contains no features.")
                gdf = gpd.GeoDataFrame.from_features(features, crs=default_crs)

    except Exception as e:
        raise ValueError(f"Failed to parse vector file: {str(e)}") from e

    # Check if empty
    if gdf is None or len(gdf) == 0:
        raise ValueError("Dataset contains zero features or records.")

    if "geometry" not in gdf.columns or gdf.geometry.isnull().all():
        raise ValueError("Dataset has no valid geometry column.")

    # Drop null geometries with warning
    null_count = gdf.geometry.isnull().sum()
    if null_count > 0:
        warning_msg = f"Removed {null_count} feature(s) with missing geometries."
        gdf = gdf.dropna(subset=["geometry"])

    if len(gdf) == 0:
        raise ValueError("Dataset contains no valid geometry features after removing nulls.")

    # Validate and repair geometries
    invalid_mask = ~gdf.geometry.is_valid
    invalid_count = invalid_mask.sum()
    if invalid_count > 0:
        if auto_repair:
            gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if not g.is_valid else g)
            repair_note = f"Auto-repaired {invalid_count} invalid geometry/geometries."
            warning_msg = f"{warning_msg} {repair_note}" if warning_msg else repair_note
        else:
            warning_msg = f"Warning: {invalid_count} invalid geometries detected."

    # Handle CRS
    if gdf.crs is None:
        gdf.set_crs(default_crs, inplace=True)
        crs_note = f"Dataset was missing CRS; defaulted to {default_crs} (WGS84 lat/lon)."
        warning_msg = f"{warning_msg} {crs_note}" if warning_msg else crs_note

    return gdf, warning_msg


def inspect_vector_dataset(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """
    Extracts summary metadata for display in the dashboard.
    """
    if gdf is None or len(gdf) == 0:
        return {
            "feature_count": 0,
            "geom_types": [],
            "crs": "None",
            "bounds": None,
            "columns": [],
        }

    geom_types = list(gdf.geometry.geom_type.unique())
    crs_str = gdf.crs.to_string() if gdf.crs else "Unspecified"
    total_bounds = gdf.total_bounds.tolist() if len(gdf) > 0 else None

    # Calculate approximate centroid in WGS84 for map centering
    try:
        wgs_gdf = gdf.to_crs(epsg=4326)
        union_geom = wgs_gdf.union_all() if hasattr(wgs_gdf, "union_all") else wgs_gdf.unary_union
        centroid = union_geom.centroid
        center_coords = [centroid.y, centroid.x]
    except Exception:
        center_coords = [27.0, 85.0]  # Default Nepal Terai approx

    return {
        "feature_count": len(gdf),
        "geom_types": geom_types,
        "crs": crs_str,
        "bounds": total_bounds,
        "center": center_coords,
        "columns": [col for col in gdf.columns if col != "geometry"],
    }


def export_gdf_to_geojson_string(gdf: gpd.GeoDataFrame) -> str:
    """
    Serializes a GeoDataFrame to a clean GeoJSON string for downloading.
    Always reprojects to EPSG:4326 for standard GeoJSON compliance (RFC 7946).
    """
    if gdf is None or len(gdf) == 0:
        return json.dumps({"type": "FeatureCollection", "features": []})

    export_gdf = gdf.copy()
    if export_gdf.crs and export_gdf.crs.to_epsg() != 4326:
        export_gdf = export_gdf.to_crs(epsg=4326)

    # Convert timestamps and non-serializable columns
    for col in export_gdf.columns:
        if col != "geometry":
            if pd.api.types.is_datetime64_any_dtype(export_gdf[col]):
                export_gdf[col] = export_gdf[col].astype(str)

    return export_gdf.to_json(indent=2)
