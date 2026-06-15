# -*- coding: utf-8 -*-
"""
clic_map_cast.py
Map tool: captures a canvas click, finds candidate CORONA passes from the
cached capabilities, confirms real coverage via GetFeatureInfo (in a
background thread), then shows the results dialog.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import QApplication
from qgis.gui import QgsMapToolEmitPoint
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    Qgis,
)
from qgis.utils import iface

from . import capabilities as caps
from . import coverage
from .corona_results_dialog import CoronaResultsDialog

CAST_WEB = "https://corona.cast.uark.edu/atlas#zoom=16&center={x:.4f},{y:.4f}"


# ================================================================== #
#  Background worker — candidate filtering + coverage confirmation    #
# ================================================================== #

class CoverageWorker(QThread):
    finished = pyqtSignal(list)   # list of confirmed pass names
    error    = pyqtSignal(str)

    def __init__(self, layers, lon, lat):
        super().__init__()
        self.layers = layers
        self.lon = lon
        self.lat = lat

    def run(self):
        try:
            candidates = caps.candidate_layers(
                self.layers, self.lon, self.lat,
                max_area=600.0, passes_only=True
            )
            confirmed = coverage.confirm_coverage(
                candidates, self.lon, self.lat
            )
            self.finished.emit(confirmed)
        except Exception as e:
            self.error.emit(str(e))


# ================================================================== #
#  Map tool                                                           #
# ================================================================== #

class CoronaMapTool(QgsMapToolEmitPoint):

    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin           # reference to access cached layers
        self.setCursor(Qt.CrossCursor)
        self.worker = None

    def canvasPressEvent(self, e):
        # Need the capabilities cache loaded first
        layers = self.plugin.get_layers()
        if not layers:
            iface.messageBar().pushMessage(
                "🛰 Corona CAST",
                "Capabilities not loaded yet. Use the plugin menu → "
                "'Download / update CORONA index' first.",
                level=Qgis.Warning,
                duration=6,
            )
            return

        # ---- Transform clicked point --------------------------------
        point_canvas = self.toMapCoordinates(e.pos())
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        tr_4326 = QgsCoordinateTransform(
            canvas_crs, wgs84, QgsCoordinateTransformContext()
        )
        pt = tr_4326.transform(point_canvas)
        lon, lat = pt.x(), pt.y()

        epsg3857 = QgsCoordinateReferenceSystem("EPSG:3857")
        tr_3857 = QgsCoordinateTransform(
            canvas_crs, epsg3857, QgsCoordinateTransformContext()
        )
        pt3857 = tr_3857.transform(point_canvas)
        web_url = CAST_WEB.format(x=pt3857.x(), y=pt3857.y())

        # ---- Feedback + launch worker -------------------------------
        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            f"Checking coverage at {lat:.4f}, {lon:.4f} …",
            level=Qgis.Info,
            duration=3,
        )
        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.worker = CoverageWorker(layers, lon, lat)
        self.worker.finished.connect(
            lambda passes: self._show_dialog(passes, lat, lon, web_url)
        )
        self.worker.error.connect(
            lambda err: self._on_error(err, web_url)
        )
        self.worker.start()

    # ------------------------------------------------------------------ #

    def _show_dialog(self, passes, lat, lon, web_url):
        QApplication.restoreOverrideCursor()
        layers = self.plugin.get_layers()
        dlg = CoronaResultsDialog(
            passes=passes,
            layers=layers,
            lat=lat,
            lon=lon,
            web_url=web_url,
            parent=iface.mainWindow(),
        )
        dlg.exec()

    def _on_error(self, err, web_url):
        QApplication.restoreOverrideCursor()
        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            f"Coverage check failed: {err} — opening browser instead.",
            level=Qgis.Warning,
            duration=6,
        )
        import webbrowser
        webbrowser.open(web_url)
