"""
Interactive Map Visualization Module
FloodWatch Nepal

Builds a professional Folium GIS map with custom styling, layer controls,
dynamic popups, tooltips, and responsive legend.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import folium
from folium import Element, FeatureGroup, LayerControl
import geopandas as gpd
import pandas as pd


def _clean_gdf_for_folium(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Converts timestamps and non-serializable objects to strings to avoid folium json serialization errors."""
    if gdf is None or len(gdf) == 0:
        return gdf
    clean = gdf.copy()
    for col in clean.columns:
        if col != "geometry":
            if pd.api.types.is_datetime64_any_dtype(clean[col]) or "datetime" in str(clean[col].dtype).lower():
                clean[col] = clean[col].astype(str)
    return clean


def get_map_bounds_and_center(
    gdfs: List[gpd.GeoDataFrame],
) -> tuple[list[float], list[list[float]]]:
    """
    Computes unified center and bounding box for all provided GeoDataFrames.
    """
    valid_gdfs = [gdf for gdf in gdfs if gdf is not None and len(gdf) > 0]
    if not valid_gdfs:
        # Default center to Nepal Terai (Sunsari / Koshi region)
        return [26.65, 87.15], [[26.4, 86.8], [26.9, 87.5]]

    total_bounds_list = []
    for g in valid_gdfs:
        g_wgs = g.to_crs(epsg=4326) if g.crs and g.crs.to_epsg() != 4326 else g
        total_bounds_list.append(g_wgs.total_bounds)  # [minx, miny, maxx, maxy]

    minx = min(b[0] for b in total_bounds_list)
    miny = min(b[1] for b in total_bounds_list)
    maxx = max(b[2] for b in total_bounds_list)
    maxy = max(b[3] for b in total_bounds_list)

    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]
    bounds = [[miny, minx], [maxy, maxx]]
    return center, bounds


def create_flood_map(
    flood_gdf: Optional[gpd.GeoDataFrame] = None,
    settlement_gdf: Optional[gpd.GeoDataFrame] = None,
    study_area_gdf: Optional[gpd.GeoDataFrame] = None,
    zoom_start: int = 12,
    show_legend: bool = True,
) -> folium.Map:
    """
    Generates a Folium interactive map for flood and settlement exposure visualization.

    Color scheme:
    - Flood: Cyan/Deep Blue (#00b4d8 / #0077b6)
    - Exposed settlements: Crimson / Orange-Red (#e63946 / #d90429)
    - Unexposed settlements: Neutral Slate / Teal (#6c757d / #2a9d8f)
    - Study area: Dashed Navy boundary (#1d3557)
    """
    active_gdfs = [g for g in [flood_gdf, settlement_gdf, study_area_gdf] if g is not None and len(g) > 0]
    center, bounds = get_map_bounds_and_center(active_gdfs)

    # Base Folium Map - Default to OpenStreetMap (no API key required)
    fmap = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )

    # Additional base layers
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="Esri Satellite Imagery",
        attr="Esri, Maxar, Earthstar Geographics",
    ).add_to(fmap)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        name="Humanitarian OpenStreetMap (HOT)",
        attr="OpenStreetMap contributors, Humanitarian OpenStreetMap Team",
    ).add_to(fmap)

    # 1. Study Area Layer
    if study_area_gdf is not None and len(study_area_gdf) > 0:
        study_wgs = study_area_gdf.to_crs(epsg=4326) if study_area_gdf.crs and study_area_gdf.crs.to_epsg() != 4326 else study_area_gdf
        study_wgs = _clean_gdf_for_folium(study_wgs)
        study_group = FeatureGroup(name="Terai Study Area Boundary", show=True)

        study_fields = [c for c in ["district", "name", "region", "province"] if c in study_wgs.columns]
        study_aliases = [f"{c.title()}: " for c in study_fields]
        study_tooltip = folium.GeoJsonTooltip(fields=study_fields, aliases=study_aliases, localize=True) if study_fields else None

        folium.GeoJson(
            study_wgs,
            name="Terai Boundary",
            style_function=lambda feature: {
                "fillColor": "#457b9d",
                "color": "#1d3557",
                "weight": 2.5,
                "dashArray": "6, 6",
                "fillOpacity": 0.05,
            },
            tooltip=study_tooltip,
        ).add_to(study_group)
        study_group.add_to(fmap)

    # 2. Flood Extent Layer
    if flood_gdf is not None and len(flood_gdf) > 0:
        flood_wgs = flood_gdf.to_crs(epsg=4326) if flood_gdf.crs and flood_gdf.crs.to_epsg() != 4326 else flood_gdf
        flood_wgs = _clean_gdf_for_folium(flood_wgs)
        flood_group = FeatureGroup(name="Flood Extent (Inundation)", show=True)

        flood_fields = [c for c in ["event_name", "date", "source", "area_km2", "severity"] if c in flood_wgs.columns]
        flood_aliases = [f"{f.replace('_', ' ').title()}: " for f in flood_fields]
        flood_tooltip = folium.GeoJsonTooltip(fields=flood_fields, aliases=flood_aliases, localize=True, sticky=True) if flood_fields else None

        folium.GeoJson(
            flood_wgs,
            name="Flood Extent",
            style_function=lambda feature: {
                "fillColor": "#00b4d8",
                "color": "#0077b6",
                "weight": 2.0,
                "fillOpacity": 0.60,
            },
            highlight_function=lambda feature: {
                "fillColor": "#90e0ef",
                "color": "#03045e",
                "weight": 3.0,
                "fillOpacity": 0.85,
            },
            tooltip=flood_tooltip,
        ).add_to(flood_group)
        flood_group.add_to(fmap)

    # 3. Settlement & Building Features Layer
    if settlement_gdf is not None and len(settlement_gdf) > 0:
        settle_wgs = settlement_gdf.to_crs(epsg=4326) if settlement_gdf.crs and settlement_gdf.crs.to_epsg() != 4326 else settlement_gdf
        settle_wgs = _clean_gdf_for_folium(settle_wgs)

        # Create separate groups for Exposed and Unexposed for crisp toggleability
        exposed_group = FeatureGroup(name="Potentially Exposed Settlements", show=True)
        safe_group = FeatureGroup(name="Unexposed Settlements", show=True)

        # Style function for Polygons
        def settlement_style(feature):
            props = feature.get("properties", {})
            exposed = props.get("is_exposed", False)
            if exposed:
                risk = props.get("risk_level", "High Exposure")
                fill = "#e63946" if "High" in risk else "#f77f00"
                return {
                    "fillColor": fill,
                    "color": "#9d0208",
                    "weight": 2.2,
                    "fillOpacity": 0.70,
                }
            else:
                return {
                    "fillColor": "#adb5bd",
                    "color": "#495057",
                    "weight": 1.2,
                    "fillOpacity": 0.35,
                }

        # Separate into points and polygons/multipolygons to support mixed geometry datasets cleanly
        points_gdf = settle_wgs[settle_wgs.geometry.geom_type.isin(["Point", "MultiPoint"])]
        polys_gdf = settle_wgs[~settle_wgs.geometry.geom_type.isin(["Point", "MultiPoint"])]

        tooltip_fields = [
            c for c in ["name", "settlement_name", "district", "municipality", "feature_type",
                        "exposure_status", "exposure_percentage", "flooded_area_ha", "risk_level"]
            if c in settle_wgs.columns
        ]
        tooltip_aliases = [f"{c.replace('_', ' ').title()}: " for c in tooltip_fields]

        # 3a. Render Points (e.g. schools, health facilities, shelter points)
        if len(points_gdf) > 0:
            for _, row in points_gdf.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                exposed = bool(row.get("is_exposed", False))
                color = "#d90429" if exposed else "#2a9d8f"
                fill_color = "#ef233c" if exposed else "#48cae4"
                radius = 7 if exposed else 5

                # HTML Popup
                name = row.get("name", row.get("settlement_name", "Settlement Point"))
                status = "POTENTIALLY EXPOSED" if exposed else "SAFE / OUTSIDE FLOOD"
                status_color = "#d90429" if exposed else "#2a9d8f"

                popup_html = f"""
                <div style="font-family: Arial, sans-serif; min-width: 180px;">
                    <div style="font-size: 14px; font-weight: bold; margin-bottom: 4px; color: #1d3557;">{name}</div>
                    <div style="display: inline-block; padding: 2px 6px; border-radius: 4px; background: {status_color}; color: white; font-size: 11px; font-weight: bold; margin-bottom: 6px;">
                        {status}
                    </div>
                    <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                """
                for field in tooltip_fields:
                    if field not in ("name", "settlement_name", "geometry"):
                        val = row.get(field, "N/A")
                        popup_html += f"<tr><td style='color: #666; padding: 2px 0;'>{field.replace('_', ' ').title()}:</td><td style='font-weight: 600; text-align: right;'>{val}</td></tr>"
                popup_html += "</table></div>"

                pt_coord = [geom.centroid.y, geom.centroid.x]
                marker = folium.CircleMarker(
                    location=pt_coord,
                    radius=radius,
                    color=color,
                    weight=2,
                    fill=True,
                    fill_color=fill_color,
                    fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{name} ({status})"
                )

                if exposed:
                    marker.add_to(exposed_group)
                else:
                    marker.add_to(safe_group)

        # 3b. Render Polygons (e.g. settlement boundaries, urban cluster footprints)
        if len(polys_gdf) > 0:
            if "is_exposed" in polys_gdf.columns:
                exposed_poly_gdf = polys_gdf[polys_gdf["is_exposed"] == True]
                safe_poly_gdf = polys_gdf[polys_gdf["is_exposed"] == False]
            else:
                exposed_poly_gdf = polys_gdf
                safe_poly_gdf = gpd.GeoDataFrame(columns=polys_gdf.columns, crs=polys_gdf.crs)

            if len(exposed_poly_gdf) > 0:
                exposed_poly_gdf = _clean_gdf_for_folium(exposed_poly_gdf)
                folium.GeoJson(
                    exposed_poly_gdf,
                    name="Potentially Exposed Settlement Footprints",
                    style_function=settlement_style,
                    highlight_function=lambda f: {"weight": 3.5, "fillOpacity": 0.9},
                    tooltip=folium.GeoJsonTooltip(
                        fields=tooltip_fields,
                        aliases=tooltip_aliases,
                        localize=True,
                    ) if tooltip_fields else None,
                ).add_to(exposed_group)

            if len(safe_poly_gdf) > 0:
                safe_poly_gdf = _clean_gdf_for_folium(safe_poly_gdf)
                folium.GeoJson(
                    safe_poly_gdf,
                    name="Unexposed Settlement Footprints",
                    style_function=settlement_style,
                    highlight_function=lambda f: {"weight": 2.5, "fillOpacity": 0.6},
                    tooltip=folium.GeoJsonTooltip(
                        fields=tooltip_fields,
                        aliases=tooltip_aliases,
                        localize=True,
                    ) if tooltip_fields else None,
                ).add_to(safe_group)

        exposed_group.add_to(fmap)
        safe_group.add_to(fmap)

    # Auto-fit bounds
    if active_gdfs:
        fmap.fit_bounds(bounds, padding=[20, 20])

    # Layer Control
    LayerControl(position="topright", collapsed=False).add_to(fmap)

    # 4. Custom Floating HTML Legend
    if show_legend:
        legend_html = """
        <div style="
            position: fixed; 
            bottom: 30px; 
            right: 30px; 
            width: 250px; 
            z-index: 9999; 
            background: white; 
            padding: 12px 16px; 
            border-radius: 8px; 
            box-shadow: 0 4px 14px rgba(0,0,0,0.22);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 12px;
            color: #212529;
            border-left: 4px solid #1d3557;
        ">
            <div style="font-weight: 700; font-size: 13px; color: #0a192f; margin-bottom: 8px;">
                Map Legend
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="display: inline-block; width: 18px; height: 14px; background: #00b4d8; opacity: 0.7; border: 1.5px solid #0077b6; border-radius: 2px; margin-right: 8px;"></span>
                <span>Flood Inundation Extent</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="display: inline-block; width: 18px; height: 14px; background: #ef233c; opacity: 0.85; border: 1.5px solid #9d0208; border-radius: 2px; margin-right: 8px;"></span>
                <span><strong>Potentially Exposed</strong> Feature</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="display: inline-block; width: 18px; height: 14px; background: #adb5bd; opacity: 0.5; border: 1.5px solid #495057; border-radius: 2px; margin-right: 8px;"></span>
                <span>Unexposed Settlement</span>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="display: inline-block; width: 18px; height: 3px; background: #1d3557; border-top: 1px dashed #1d3557; margin-right: 8px;"></span>
                <span>Study Area Boundary</span>
            </div>
            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #e9ecef; font-size: 10px; color: #6c757d; line-height: 1.3;">
                Indicative spatial intersection. Does not represent confirmed damage.
            </div>
        </div>
        """
        fmap.get_root().html.add_child(Element(legend_html))

    return fmap
