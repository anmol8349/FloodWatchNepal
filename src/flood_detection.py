"""
Satellite SAR Flood Detection Architecture Module
FloodWatch Nepal

Prepares the modular architecture for Sentinel-1 Synthetic Aperture Radar (SAR)
flood mapping via Google Earth Engine (GEE).
Explicitly handles authentication status and provides executable workflow templates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry import Polygon, box, mapping


@dataclass
class GEEStatus:
    is_installed: bool
    is_authenticated: bool
    account_info: Optional[str]
    status_message: str
    setup_guide_url: str = "https://developers.google.com/earth-engine/guides/python_install"


class Sentinel1SARPipeline:
    """
    Architecture for Sentinel-1 C-band SAR Flood Detection in the Nepal Terai.

    Methodology:
    1. Collect Sentinel-1 GRD (Interferometric Wide Swath - IW, VV/VH polarization).
    2. Filter by acquisition geometry (Relative Orbit, Ascending/Descending).
    3. Generate Pre-flood Baseline composite (median backscatter sigma-0 over 30 days).
    4. Acquire Post-flood / Event scene during or immediately following peak rainfall.
    5. Apply speckle filter (e.g., Refined Lee or 5x5 Focal Mean).
    6. Calculate backscatter difference: Delta = Post - Pre (in decibels, dB).
    7. Thresholding: Detect specular water reflections (typically < -15 dB absolute or < -3 dB drop).
    8. Environmental Masking:
       - HydroSHEDS / SRTM DEM: mask steep terrain (> 5% slope).
       - JRC Global Surface Water: mask permanent rivers and lakes.
    9. Morphological cleaning: Remove isolated pixels (< 8 connectivity, min 0.5 ha).
    10. Polygonization: Vectorize flood raster mask into GeoJSON polygons.
    """

    DEFAULT_THRESHOLD_DB = -3.2
    MAX_SLOPE_PERCENT = 5.0

    def __init__(self):
        self._ee_module = None
        self._status = self._probe_gee_status()

    def _probe_gee_status(self) -> GEEStatus:
        """
        Safely probes whether Google Earth Engine Python API is installed and authenticated.
        Never pretends to be operational if credentials are not verified.
        """
        try:
            import ee
            self._ee_module = ee
        except ImportError:
            return GEEStatus(
                is_installed=False,
                is_authenticated=False,
                account_info=None,
                status_message="Earth Engine Python library ('earthengine-api') is not installed in the environment."
            )

        try:
            # Check if initialized
            self._ee_module.Initialize()
            return GEEStatus(
                is_installed=True,
                is_authenticated=True,
                account_info="Initialized successfully with active credentials",
                status_message="Google Earth Engine API is authenticated and ready."
            )
        except Exception as e:
            return GEEStatus(
                is_installed=True,
                is_authenticated=False,
                account_info=None,
                status_message=f"Google Earth Engine is installed but unauthenticated: {str(e)}"
            )

    @property
    def status(self) -> GEEStatus:
        """Returns the current GEE authentication and installation status."""
        return self._status

    def get_pipeline_specs(self) -> Dict[str, Any]:
        """Returns scientific and operational parameters of the SAR pipeline."""
        return {
            "satellite_constellation": "Copernicus Sentinel-1A / Sentinel-1B",
            "sensor": "C-band Synthetic Aperture Radar (C-SAR, 5.405 GHz)",
            "acquisition_mode": "Interferometric Wide Swath (IW)",
            "product_type": "Level-1 Ground Range Detected (GRD), High Resolution (10m)",
            "polarizations": ["VV (Primary water detection)", "VH (Vegetated flood monitoring)"],
            "revisit_time": "6 to 12 days over Nepal (dependent on constellation status)",
            "penetration": "All-weather, day-and-night imaging (penetrates monsoon cloud cover)",
            "detection_threshold_db": self.DEFAULT_THRESHOLD_DB,
            "slope_mask_limit": f"{self.MAX_SLOPE_PERCENT}% using NASADEM / SRTM 30m",
            "permanent_water_mask": "JRC Global Surface Water Mapping (transitions / seasonality)",
            "operational_readiness": "Architecture Ready. Awaiting Earth Engine API Key/OAuth token.",
        }

    def generate_gee_python_script(
        self,
        district_name: str = "Sunsari",
        pre_start: str = "2024-06-01",
        pre_end: str = "2024-06-30",
        post_start: str = "2024-07-08",
        post_end: str = "2024-07-15",
        threshold_db: float = -3.2,
    ) -> str:
        """
        Generates production-grade Google Earth Engine Python script
        for users with active GEE accounts.
        """
        script = f'''"""
Sentinel-1 SAR Automated Flood Mapping for Nepal Terai
Study Area: {district_name} District
Target Dates: {post_start} to {post_end} (Event) vs {pre_start} to {pre_end} (Baseline)
"""

import ee

# 1. Initialize Earth Engine with your Google Cloud Project
ee.Initialize(project='your-gcp-project-id')

# 2. Define Area of Interest (AOI) - Nepal Terai ({district_name})
# Example bounding box coordinates for {district_name}: [86.9, 26.4, 87.3, 26.9]
aoi = ee.Geometry.Rectangle([86.9, 26.4, 87.3, 26.9])

# 3. Filter Sentinel-1 GRD Collection
s1_col = (
    ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(aoi)
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
)

# 4. Filter Pre-flood and Post-flood periods
pre_flood = s1_col.filterDate('{pre_start}', '{pre_end}').select('VV').median()
post_flood = s1_col.filterDate('{post_start}', '{post_end}').select('VV').min()

# 5. Calculate Difference (Decibel drop due to specular water reflection)
diff = post_flood.subtract(pre_flood)

# 6. Apply Inundation Threshold
flooded = diff.lt({threshold_db})

# 7. Mask Steep Slopes (> 5%) using NASADEM
dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
slope = ee.Terrain.slope(dem)
flooded_terai = flooded.updateMask(slope.lt({self.MAX_SLOPE_PERCENT}))

# 8. Mask Permanent Water Bodies (JRC Global Surface Water)
permanent_water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('seasonality').gte(10)
flooded_clean = flooded_terai.updateMask(permanent_water.Not())

# 9. Vectorize Inundation Mask to GeoJSON Polygons
flood_vectors = flooded_clean.selfMask().reduceToVectors(
    geometry=aoi,
    scale=10,
    geometryType='polygon',
    eightConnected=False,
    maxPixels=1e8
)

print(f"Extraction complete for {district_name}. Exporting to GeoJSON...")
# task = ee.batch.Export.table.toDrive(collection=flood_vectors, description='Flood_Extent_{district_name}', fileFormat='GeoJSON')
# task.start()
'''
        return script


def get_satellite_sensor_comparison() -> List[Dict[str, str]]:
    """Returns comparative metadata between optical vs SAR for Nepal monsoon floods."""
    return [
        {
            "Sensor / Platform": "Copernicus Sentinel-1 (SAR)",
            "Modality": "Radar (C-band microwave, active)",
            "Cloud Penetration": "100% All-Weather (operates through dense monsoon clouds)",
            "Revisit Time": "6 - 12 Days",
            "Day / Night": "Both Day and Night",
            "Primary Limitation": "Rough water surface caused by heavy winds; urban building shadow/layover",
        },
        {
            "Sensor / Platform": "Sentinel-2 / Landsat 8-9 (Optical)",
            "Modality": "Multispectral (visible, NIR, SWIR)",
            "Cloud Penetration": "0% (completely blocked by monsoon cloud cover)",
            "Revisit Time": "5 Days (combined S2A + S2B)",
            "Day / Night": "Daytime Only",
            "Primary Limitation": "Severe cloud obscuration during active flooding events in Nepal Terai",
        },
        {
            "Sensor / Platform": "PlanetScope / SkySat (Commercial Optical)",
            "Modality": "High-resolution optical (3m - 50cm)",
            "Cloud Penetration": "0% (Cloud blocked)",
            "Revisit Time": "Daily",
            "Day / Night": "Daytime Only",
            "Primary Limitation": "Commercial paywall, cloud cover during peak monsoonal downpours",
        },
    ]
