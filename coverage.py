# -*- coding: utf-8 -*-
"""
coverage.py
Confirms whether CORONA layers actually have pixel data at a point,
using WMS GetFeatureInfo (which reads the cached imagery, NOT the
broken footprints database).

Runs the checks in parallel for speed.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WMS_BASE = "https://geoserve.cast.uark.edu/geoserver/corona/wms"


def _featureinfo_url(layer_name, lon, lat, d=0.02):
    return (
        f"{WMS_BASE}"
        "?service=WMS&version=1.1.1&request=GetFeatureInfo"
        f"&layers=corona:{layer_name}&query_layers=corona:{layer_name}"
        "&info_format=application/json&srs=EPSG:4326"
        f"&bbox={lon-d},{lat-d},{lon+d},{lat+d}"
        "&width=11&height=11&x=5&y=5&feature_count=5"
    )


def _check_one(layer_name, lon, lat, timeout=20):
    """
    Returns (layer_name, True/False/None).
    True  = imagery present at point
    False = no imagery (transparent / outside footprint)
    None  = request failed
    """
    url = _featureinfo_url(layer_name, lon, lat)
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "QGIS-CoronaCastPlugin/2.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        feats = data.get("features", [])
        # Imagery present if any GRAY_INDEX is non-zero
        for f in feats:
            val = f.get("properties", {}).get("GRAY_INDEX", 0)
            if val and val != 0:
                return (layer_name, True)
        return (layer_name, False)
    except Exception:
        return (layer_name, None)


def confirm_coverage(layer_names, lon, lat, max_workers=20, timeout=20):
    """
    Check a list of layer names in parallel.
    Returns a list of names that actually have imagery at (lon, lat).
    """
    confirmed = []
    if not layer_names:
        return confirmed

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_check_one, name, lon, lat, timeout): name
            for name in layer_names
        }
        for fut in as_completed(futures):
            name, has_data = fut.result()
            if has_data:
                confirmed.append(name)

    return sorted(confirmed)
