"""
Flood Impact Assessment Module
FloodWatch Nepal

Calculates spatial intersections, flooded areas in km², settlement exposure percentages,
and risk categorization using GeoPandas and Shapely in appropriate metric projections.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union


DISCLAIMER_TEXT = (
    "EXPOSURE NOTICE: Features labeled as 'Potentially Exposed' intersect the spatial flood extent. "
    "Spatial exposure indicates inundation risk, NOT verified structural damage or casualty statistics. "
    "Ground verification and field surveys are required for damage verification."
)


def _safe_union(gdf: gpd.GeoDataFrame):
    """Safely calculates the geometric union, supporting both new GeoPandas union_all and unary_union."""
    if hasattr(gdf, "union_all"):
        return gdf.union_all()
    elif hasattr(gdf, "unary_union"):
        return gdf.unary_union
    else:
        valid_geoms = [g for g in gdf.geometry if g is not None and not g.is_empty]
        return unary_union(valid_geoms)


def get_optimal_nepal_utm_crs(gdf: gpd.GeoDataFrame) -> str:
    """
    Selects the optimal Universal Transverse Mercator (UTM) zone for Nepal datasets.
    - UTM Zone 44N (EPSG:32644): Western Nepal (78°E to 84°E)
    - UTM Zone 45N (EPSG:32645): Central & Eastern Nepal (84°E to 90°E)

    Falls back to EPSG:3857 (Web Mercator) if coordinates are outside Nepal or invalid.
    """
    try:
        # Reproject temporarily to WGS84 to inspect longitude
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            wgs_gdf = gdf.to_crs(epsg=4326)
        else:
            wgs_gdf = gdf

        combined = _safe_union(wgs_gdf)
        centroid = combined.centroid
        lon = centroid.x

        if 78.0 <= lon < 84.0:
            return "EPSG:32644"  # Nepal UTM Zone 44N
        elif 84.0 <= lon <= 90.0:
            return "EPSG:32645"  # Nepal UTM Zone 45N
        else:
            # Generic UTM calculation for global regions
            zone_number = int((lon + 180) / 6) + 1
            if centroid.y >= 0:
                return f"EPSG:326{zone_number:02d}"
            else:
                return f"EPSG:327{zone_number:02d}"
    except Exception:
        return "EPSG:32645"  # Default to Nepal Zone 45N (covers Koshi, Terai east)


def calculate_flood_extent_metrics(
    flood_gdf: gpd.GeoDataFrame,
    target_crs: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculates total flooded area in square kilometers and hectares.
    Dissolves multi-part or overlapping flood polygons to avoid double counting.
    """
    if flood_gdf is None or len(flood_gdf) == 0:
        return {
            "flood_area_km2": 0.0,
            "flood_area_ha": 0.0,
            "flood_polygon_count": 0,
            "metric_crs": target_crs or "None",
        }

    if target_crs is None:
        target_crs = get_optimal_nepal_utm_crs(flood_gdf)

    # Project to metric CRS
    flood_proj = flood_gdf.to_crs(target_crs)

    # Clean geometries
    valid_geoms = [g for g in flood_proj.geometry if g is not None and not g.is_empty]
    if not valid_geoms:
        return {
            "flood_area_km2": 0.0,
            "flood_area_ha": 0.0,
            "flood_polygon_count": 0,
            "metric_crs": target_crs,
        }

    # Dissolve overlapping polygons for exact unique footprint area
    flood_union = _safe_union(flood_proj)
    area_m2 = flood_union.area
    area_km2 = round(area_m2 / 1_000_000.0, 4)
    area_ha = round(area_m2 / 10_000.0, 2)

    return {
        "flood_area_km2": area_km2,
        "flood_area_ha": area_ha,
        "flood_polygon_count": len(flood_gdf),
        "metric_crs": target_crs,
    }


def assess_settlement_impact(
    flood_gdf: gpd.GeoDataFrame,
    settlement_gdf: gpd.GeoDataFrame,
    target_crs: Optional[str] = None,
) -> Tuple[gpd.GeoDataFrame, Dict[str, Any]]:
    """
    Performs spatial intersection between flood extent and settlement/building geometries.

    Returns:
        enriched_gdf: GeoDataFrame in EPSG:4326 with exposure status, flooded area,
                      exposure percentage, and risk classification.
        metrics: Summary dictionary with key statistics for dashboard cards.
    """
    if settlement_gdf is None or len(settlement_gdf) == 0:
        empty_gdf = gpd.GeoDataFrame(columns=["is_exposed", "exposure_status", "geometry"], crs="EPSG:4326")
        empty_metrics = {
            "total_settlements": 0,
            "exposed_count": 0,
            "exposed_polygons": 0,
            "exposed_points": 0,
            "flood_area_km2": 0.0,
            "settlement_exposure_pct": 0.0,
            "total_settlement_area_km2": 0.0,
            "exposed_settlement_area_km2": 0.0,
            "metric_crs": target_crs or "EPSG:32645",
            "disclaimer": DISCLAIMER_TEXT,
        }
        return empty_gdf, empty_metrics

    # Choose compatible metric CRS
    if target_crs is None:
        target_crs = get_optimal_nepal_utm_crs(settlement_gdf)

    # Calculate flood area
    flood_metrics = calculate_flood_extent_metrics(flood_gdf, target_crs=target_crs)
    flood_area_km2 = flood_metrics["flood_area_km2"]

    # Reproject both datasets to metric UTM CRS
    settlements_proj = settlement_gdf.to_crs(target_crs).copy()

    # If no flood data, mark all as unexposed
    if flood_gdf is None or len(flood_gdf) == 0:
        res = settlements_proj.copy()
        res["is_exposed"] = False
        res["exposure_status"] = "Not Exposed"
        res["flooded_area_ha"] = 0.0
        res["exposure_percentage"] = 0.0
        res["risk_level"] = "None"
        res_wgs = res.to_crs(epsg=4326)
        metrics = {
            "total_settlements": len(res_wgs),
            "exposed_count": 0,
            "exposed_polygons": 0,
            "exposed_points": 0,
            "flood_area_km2": 0.0,
            "settlement_exposure_pct": 0.0,
            "total_settlement_area_km2": 0.0,
            "exposed_settlement_area_km2": 0.0,
            "metric_crs": target_crs,
            "disclaimer": DISCLAIMER_TEXT,
        }
        return res_wgs, metrics

    flood_proj = flood_gdf.to_crs(target_crs)
    flood_union = _safe_union(flood_proj)

    # Initialize analysis columns
    is_exposed = []
    exposure_status = []
    flooded_area_ha_list = []
    exposure_pct_list = []
    risk_level_list = []

    polygon_features = 0
    exposed_polygons = 0
    point_features = 0
    exposed_points = 0

    total_settlement_area_m2 = 0.0
    total_exposed_settlement_area_m2 = 0.0

    for idx, geom in enumerate(settlements_proj.geometry):
        if geom is None or geom.is_empty or not geom.is_valid:
            is_exposed.append(False)
            exposure_status.append("Invalid / Null Geometry")
            flooded_area_ha_list.append(0.0)
            exposure_pct_list.append(0.0)
            risk_level_list.append("None")
            continue

        g_type = geom.geom_type

        if g_type in ("Polygon", "MultiPolygon"):
            polygon_features += 1
            orig_area = geom.area
            total_settlement_area_m2 += orig_area

            # Intersect with flood extent
            if geom.intersects(flood_union):
                intersection = geom.intersection(flood_union)
                intersect_area = intersection.area
                total_exposed_settlement_area_m2 += intersect_area

                pct = round(min(100.0, (intersect_area / orig_area) * 100.0), 2) if orig_area > 0 else 0.0
                ha = round(intersect_area / 10_000.0, 4)

                is_exposed.append(True)
                exposure_status.append("Potentially Exposed")
                flooded_area_ha_list.append(ha)
                exposure_pct_list.append(pct)
                exposed_polygons += 1

                if pct >= 50.0:
                    risk_level_list.append("High Exposure")
                elif pct >= 20.0:
                    risk_level_list.append("Moderate Exposure")
                else:
                    risk_level_list.append("Low Exposure")
            else:
                is_exposed.append(False)
                exposure_status.append("Not Exposed")
                flooded_area_ha_list.append(0.0)
                exposure_pct_list.append(0.0)
                risk_level_list.append("None")

        else:
            # Point or MultiPoint or LineString (e.g. building centroids or access roads)
            point_features += 1
            if geom.intersects(flood_union):
                is_exposed.append(True)
                exposure_status.append("Potentially Exposed")
                flooded_area_ha_list.append(0.0)  # Dimensionless point
                exposure_pct_list.append(100.0)
                risk_level_list.append("High Exposure")
                exposed_points += 1
            else:
                is_exposed.append(False)
                exposure_status.append("Not Exposed")
                flooded_area_ha_list.append(0.0)
                exposure_pct_list.append(0.0)
                risk_level_list.append("None")

    # Add enriched attributes
    settlements_proj["is_exposed"] = is_exposed
    settlements_proj["exposure_status"] = exposure_status
    settlements_proj["flooded_area_ha"] = flooded_area_ha_list
    settlements_proj["exposure_percentage"] = exposure_pct_list
    settlements_proj["risk_level"] = risk_level_list

    # Reproject back to standard EPSG:4326 for map and export
    res_wgs = settlements_proj.to_crs(epsg=4326)

    # Metrics computation
    total_count = len(res_wgs)
    exposed_count = int(res_wgs["is_exposed"].sum())

    total_settlement_area_km2 = round(total_settlement_area_m2 / 1_000_000.0, 4)
    exposed_settlement_area_km2 = round(total_exposed_settlement_area_m2 / 1_000_000.0, 4)

    if total_settlement_area_m2 > 0:
        overall_settlement_exposure_pct = round(
            (total_exposed_settlement_area_m2 / total_settlement_area_m2) * 100.0, 2
        )
    elif total_count > 0:
        overall_settlement_exposure_pct = round((exposed_count / total_count) * 100.0, 2)
    else:
        overall_settlement_exposure_pct = 0.0

    metrics = {
        "total_settlements": total_count,
        "exposed_count": exposed_count,
        "exposed_polygons": exposed_polygons,
        "exposed_points": exposed_points,
        "polygon_features": polygon_features,
        "point_features": point_features,
        "flood_area_km2": flood_area_km2,
        "settlement_exposure_pct": overall_settlement_exposure_pct,
        "total_settlement_area_km2": total_settlement_area_km2,
        "exposed_settlement_area_km2": exposed_settlement_area_km2,
        "metric_crs": target_crs,
        "disclaimer": DISCLAIMER_TEXT,
    }

    return res_wgs, metrics
