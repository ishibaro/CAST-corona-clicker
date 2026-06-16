# -*- coding: utf-8 -*-
"""
capabilities.py
Manages the GWC GetCapabilities document:
  - downloads it from the CAST server
  - caches it on disk inside the plugin folder
  - parses it into a dict of {layer_name: bbox}
  - can check whether a newer version is available

The CORONA archive almost never changes, so a disk cache is ideal.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import os
import re
import urllib.request

CAPABILITIES_URL = (
    "https://geoserve.cast.uark.edu/geoserver/gwc/service/wms"
    "?REQUEST=GetCapabilities&tiled=true"
)

# File name for the cached capabilities document
CACHE_FILENAME = "corona_capabilities.xml"


def _safe_urlopen(url, timeout):
    """
    Open an HTTPS URL only. Rejects any other scheme (file://, ftp://, etc.)
    to satisfy security scanners and avoid unexpected scheme handling.
    """
    if not url.lower().startswith("https://"):
        raise ValueError(f"Refusing to open non-HTTPS URL: {url}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "QGIS-CoronaCastPlugin/2.0"}
    )
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310


def cache_path(plugin_dir):
    """Return the full path to the cached capabilities file."""
    return os.path.join(plugin_dir, "data", CACHE_FILENAME)


def cache_exists(plugin_dir):
    return os.path.exists(cache_path(plugin_dir))


def download_capabilities(timeout=120):
    """
    Download the GetCapabilities document from the CAST server.
    Returns the raw text. Raises on failure.
    """
    with _safe_urlopen(CAPABILITIES_URL, timeout) as resp:
        return resp.read().decode("utf-8")


def save_capabilities(plugin_dir, text):
    """Save the capabilities text to the on-disk cache."""
    path = cache_path(plugin_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def load_cached_capabilities(plugin_dir):
    """Read the cached capabilities text from disk."""
    with open(cache_path(plugin_dir), "r", encoding="utf-8") as f:
        return f.read()


def parse_capabilities(text):
    """
    Parse the GWC GetCapabilities XML into a dict:
        { layer_name: (minx, miny, maxx, maxy) }
    keeping, for each layer, the SMALLEST (most precise) bounding box,
    since the same layer can appear at several pyramid levels.
    """
    layers = {}

    for block in re.findall(r"<TileSet>.*?</TileSet>", text, re.DOTALL):
        if "EPSG:4326" not in block:
            continue
        name_m = re.search(r"<Layers>(corona:[^<]+)</Layers>", block)
        bbox_m = re.search(
            r'<BoundingBox SRS="EPSG:4326" '
            r'minx="([\d.\-]+)" miny="([\d.\-]+)" '
            r'maxx="([\d.\-]+)" maxy="([\d.\-]+)"',
            block,
        )
        if not (name_m and bbox_m):
            continue

        name = name_m.group(1).replace("corona:", "")
        bbox = tuple(map(float, bbox_m.groups()))

        # Keep the smallest bbox for each layer
        if name not in layers:
            layers[name] = bbox
        else:
            if _area(bbox) < _area(layers[name]):
                layers[name] = bbox

    return layers


def _area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def is_world_bbox(b):
    """True if the bbox basically covers the whole planet (useless)."""
    return b[0] <= -179 and b[2] >= 179 and b[1] <= -89 and b[3] >= 89


def candidate_layers(layers, lon, lat, max_area=600.0, passes_only=True):
    """
    Return candidate layer names whose (coarse) bbox contains the point,
    discarding world-sized bboxes and oversized cells.

    passes_only=True keeps only satellite passes (names ending in
    'Fore' or 'Aft'), not individual frames (df / da).
    """
    out = []
    for name, b in layers.items():
        if is_world_bbox(b):
            continue
        if _area(b) > max_area:
            continue
        if not (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]):
            continue
        if passes_only and not (name.endswith("Fore") or name.endswith("Aft")):
            continue
        out.append(name)
    return sorted(out)


def frames_for_pass(layers, pass_name):
    """
    Given a pass name like '1046-1015Fore', return its individual frame
    layer names (e.g. 1046-1015df015, df016 ...).

    Frames share the mission-frame prefix but use 'df' (Fore) or 'da' (Aft).
    """
    # Extract the prefix before Fore/Aft, e.g. "1046-1015"
    prefix = pass_name.replace("Fore", "").replace("Aft", "")
    frame_tag = "df" if pass_name.endswith("Fore") else "da"

    out = []
    for name in layers:
        if name.startswith(prefix + frame_tag):
            out.append(name)
    return sorted(out)
