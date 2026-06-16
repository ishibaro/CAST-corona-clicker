# -*- coding: utf-8 -*-
"""
legacy_map_cast.py
"Click & Go" — the original Corona Clicker behaviour.
Click the map → open the Corona CAST Atlas in the browser at that point.
No coverage check, no dialog. Fast and simple.

A tribute to the original plugin (v0.1).
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import webbrowser

from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsMapToolEmitPoint
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    Qgis,
)
from qgis.utils import iface

CAST_WEB = "https://corona.cast.uark.edu/atlas#zoom=16&center={x:.4f},{y:.4f}"


class LegacyMapTool(QgsMapToolEmitPoint):
    """Original click-and-open-browser tool."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.setCursor(Qt.CrossCursor)

    def canvasPressEvent(self, e):
        # Clicked point in canvas CRS
        point_canvas = self.toMapCoordinates(e.pos())
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        # Transform to EPSG:3857 for the CAST URL
        epsg3857 = QgsCoordinateReferenceSystem("EPSG:3857")
        transform = QgsCoordinateTransform(
            canvas_crs, epsg3857, QgsCoordinateTransformContext()
        )
        pt = transform.transform(point_canvas)

        url = CAST_WEB.format(x=pt.x(), y=pt.y())
        webbrowser.open(url)

        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            f"Opening Corona CAST Atlas at {pt.x():.1f}, {pt.y():.1f} "
            "in your browser …",
            level=Qgis.Info,
            duration=3,
        )
