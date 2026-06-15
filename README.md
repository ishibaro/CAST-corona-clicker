# 🛰 CAST Corona Clicker v2.0

A QGIS plugin to find and load declassified **CORONA spy satellite imagery
(1960–1972)** from the [Corona CAST Atlas](https://corona.cast.uark.edu/),
University of Arkansas.

---

## How it works

1. **One-time setup**: the plugin downloads a small index of all CORONA
   imagery (~12 MB) and caches it on disk. The CORONA archive almost never
   changes, so this only needs doing once.
2. **Click** anywhere on the QGIS canvas.
3. The plugin finds which satellite **passes** cover that point and
   **confirms real coverage** by querying the imagery server directly
   (not the footprints database, which is often offline).
4. A dialog shows the confirmed passes. **Expand** a pass to see its
   individual frames.
5. For any pass or frame:
   - **🗺 Add to QGIS** — loads it as a fast WMTS layer on your canvas
   - **🌐 Browser** — opens the Corona CAST Atlas at that location

---

## Why this design

CAST's footprints database (the WFS service) is frequently offline,
returning connection errors. This plugin works around that by:

- Using the **GeoWebCache GetCapabilities** for a rough first filter
  (cached on disk so the server only gets hit once)
- Confirming actual coverage with **WMS GetFeatureInfo** against the
  cached imagery tiles — fast and independent of the broken database

The result: reliable coverage checks even when CAST's main database is down.

---

## Updating the index

The CORONA archive rarely changes, but if new imagery is added you can
refresh the cached index:

**Web menu → CAST Corona Clicker → Download / update CORONA index…**

The plugin downloads the latest index, compares it with your cached copy,
tells you whether anything changed, and lets you save the new version.

---

## Services used

| Service | Purpose | Reliable? |
|---|---|---|
| GWC GetCapabilities | Index of all imagery + rough bbox | ✅ (cached) |
| WMS GetFeatureInfo | Confirm coverage at a point | ✅ |
| WMTS (GeoWebCache) | Load imagery into QGIS | ✅ |
| WFS footprints | (not used — database offline) | ❌ |

---

## Attribution

> Imagery and services provided by the **Center for Advanced Spatial
> Technologies (CAST)**, University of Arkansas.
> Casana J., Cothren J. (2013) *The CORONA Atlas Project*.
> SpringerBriefs in Archaeology.

---

## Original version created as part of

[EAMENA Project](https://eamena.org/) — Endangered Archaeology in the
Middle East and North Africa. University of Leicester / Durham University / University of Oxford.
