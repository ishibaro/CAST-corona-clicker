# -*- coding: utf-8 -*-
"""
corona_results_dialog.py
Shows confirmed CORONA passes at the clicked location in a tree.

Each pass can be expanded to its individual frames. When a pass is expanded
for the first time, its frames are checked against the click point (lazily,
in a background thread): frames that actually cover the point are shown in
bold at the top, frames that don't are shown greyed-out below.

Buttons let the user load a layer into QGIS or open the CAST atlas.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import webbrowser

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QFont, QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QDialogButtonBox,
    QFrame,
    QMessageBox,
)
from qgis.core import QgsRasterLayer, QgsProject, Qgis
from qgis.utils import iface

from . import capabilities as caps
from . import coverage

WMTS_BASE = "https://geoserve.cast.uark.edu/geoserver/gwc/service/wmts"


# ================================================================== #
#  Background worker — confirm which frames cover the point            #
# ================================================================== #

class FrameCoverageWorker(QThread):
    finished = pyqtSignal(str, list, list)   # pass_name, covering, not_covering
    error    = pyqtSignal(str, str)          # pass_name, error message

    def __init__(self, pass_name, frames, lon, lat):
        super().__init__()
        self.pass_name = pass_name
        self.frames = frames
        self.lon = lon
        self.lat = lat

    def run(self):
        try:
            covering = coverage.confirm_coverage(self.frames, self.lon, self.lat)
            covering_set = set(covering)
            not_covering = [f for f in self.frames if f not in covering_set]
            self.finished.emit(self.pass_name, covering, not_covering)
        except Exception as e:
            self.error.emit(self.pass_name, str(e))


# ================================================================== #
#  Dialog                                                             #
# ================================================================== #

class CoronaResultsDialog(QDialog):

    def __init__(self, passes, layers, lat, lon, web_url, parent=None):
        super().__init__(parent)
        self.passes = passes
        self.layers = layers
        self.lat = lat
        self.lon = lon
        self.web_url = web_url

        # Track which passes have already had their frames checked,
        # and keep references to running workers so they aren't GC'd.
        self._checked_passes = set()
        self._workers = {}

        self.setWindowTitle("🛰 CORONA Imagery — CAST Atlas")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        header = QLabel(
            f"<b>CORONA imagery at {self.lat:.5f}°, {self.lon:.5f}°</b>"
        )
        header.setAlignment(Qt.AlignCenter)
        root.addWidget(header)

        if not self.passes:
            empty = QLabel(
                "⚠️  No CORONA imagery confirmed at this location.\n\n"
                "CORONA mainly covers the Middle East, Central Asia,\n"
                "North Africa, parts of Europe, and East Asia.\n\n"
                "Try another spot, or open the Atlas to browse coverage."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            root.addWidget(empty)
        else:
            info = QLabel(
                f"<i>{len(self.passes)} satellite pass(es) cover this point. "
                f"Expand a pass to see which frames fall on the point "
                f"(shown in bold).</i>"
            )
            info.setAlignment(Qt.AlignCenter)
            info.setWordWrap(True)
            root.addWidget(info)
            self._build_tree(root)
            self._build_action_buttons(root)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        browser_btn = QPushButton("🌐  Open Corona CAST Atlas in browser")
        browser_btn.setToolTip(
            "Open the Corona CAST Atlas at this location.\n"
            "Supports CAST and lets you download original imagery."
        )
        browser_btn.clicked.connect(self._open_browser)
        root.addWidget(browser_btn)

        attr = QLabel(
            '<small>Imagery: <a href="https://corona.cast.uark.edu">'
            'Corona CAST Atlas</a>, CAST, University of Arkansas</small>'
        )
        attr.setOpenExternalLinks(True)
        attr.setAlignment(Qt.AlignCenter)
        attr.setWordWrap(True)
        root.addWidget(attr)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _build_tree(self, layout):
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Pass / Frame", "Type"])
        self.tree.setColumnWidth(0, 340)
        self.tree.setAlternatingRowColors(True)

        for pass_name in self.passes:
            mission, frame, camera = self._parse_name(pass_name)
            top = QTreeWidgetItem([
                pass_name,
                f"Mission {mission} · {camera}",
            ])
            top.setData(0, Qt.UserRole, pass_name)

            frames = caps.frames_for_pass(self.layers, pass_name)
            if frames:
                # Placeholder child so the expand arrow appears; real frames
                # are loaded lazily when the pass is first expanded.
                placeholder = QTreeWidgetItem(["(expand to check frames…)", ""])
                placeholder.setForeground(0, QBrush(QColor(140, 140, 140)))
                top.addChild(placeholder)

            self.tree.addTopLevelItem(top)

        self.tree.itemSelectionChanged.connect(self._update_button_states)
        self.tree.itemExpanded.connect(self._on_pass_expanded)
        layout.addWidget(self.tree, stretch=1)

    def _build_action_buttons(self, layout):
        row = QHBoxLayout()

        self.add_btn = QPushButton("🗺 Add selected to QGIS")
        self.add_btn.setToolTip(
            "Load the selected pass or frame as a WMTS layer in QGIS."
        )
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._add_selected)
        row.addWidget(self.add_btn)

        self.web_btn = QPushButton("🌐 Browser at point")
        self.web_btn.clicked.connect(self._open_browser)
        row.addWidget(self.web_btn)

        layout.addLayout(row)

    # ------------------------------------------------------------------ #
    #  Lazy frame checking on expand                                      #
    # ------------------------------------------------------------------ #

    def _on_pass_expanded(self, item):
        pass_name = item.data(0, Qt.UserRole)
        if not pass_name or pass_name in self._checked_passes:
            return
        self._checked_passes.add(pass_name)

        frames = caps.frames_for_pass(self.layers, pass_name)
        if not frames:
            return

        # Replace placeholder with a "checking…" note
        item.takeChildren()
        checking = QTreeWidgetItem(["⏳ checking which frames cover the point…", ""])
        checking.setForeground(0, QBrush(QColor(140, 140, 140)))
        item.addChild(checking)

        worker = FrameCoverageWorker(pass_name, frames, self.lon, self.lat)
        worker.finished.connect(self._on_frames_checked)
        worker.error.connect(self._on_frames_error)
        self._workers[pass_name] = worker
        worker.start()

    def _find_top_item(self, pass_name):
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.UserRole) == pass_name:
                return it
        return None

    def _on_frames_checked(self, pass_name, covering, not_covering):
        top = self._find_top_item(pass_name)
        if top is None:
            return

        top.takeChildren()

        bold = QFont()
        bold.setBold(True)
        grey = QBrush(QColor(150, 150, 150))

        # Frames that cover the point — bold, on top
        for fr in covering:
            child = QTreeWidgetItem([fr, "frame · on point ✓"])
            child.setData(0, Qt.UserRole, fr)
            child.setFont(0, bold)
            top.addChild(child)

        # Frames that don't — greyed out, below
        for fr in not_covering:
            child = QTreeWidgetItem([fr, "frame · off point"])
            child.setData(0, Qt.UserRole, fr)
            child.setForeground(0, grey)
            child.setForeground(1, grey)
            top.addChild(child)

        if not covering and not not_covering:
            note = QTreeWidgetItem(["(no individual frames listed)", ""])
            note.setForeground(0, grey)
            top.addChild(note)

        self._workers.pop(pass_name, None)

    def _on_frames_error(self, pass_name, err):
        top = self._find_top_item(pass_name)
        if top is not None:
            top.takeChildren()
            # Fall back to showing all frames unfiltered
            grey = QBrush(QColor(150, 150, 150))
            for fr in caps.frames_for_pass(self.layers, pass_name):
                child = QTreeWidgetItem([fr, "frame"])
                child.setData(0, Qt.UserRole, fr)
                top.addChild(child)
            note = QTreeWidgetItem([f"(could not filter frames: {err})", ""])
            note.setForeground(0, grey)
            top.addChild(note)
        self._workers.pop(pass_name, None)

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _update_button_states(self):
        items = self.tree.selectedItems()
        # Enable only if a selected item has a real layer name
        ok = any(it.data(0, Qt.UserRole) for it in items)
        self.add_btn.setEnabled(ok)

    def _add_selected(self):
        for item in self.tree.selectedItems():
            layer_name = item.data(0, Qt.UserRole)
            if layer_name:
                self._add_wmts_layer(layer_name)

    def _add_wmts_layer(self, layer_name):
        """Load a CORONA image as a WMTS layer via GeoWebCache.

        Uses PNG (which supports transparency) and renders the white
        'no data' fill transparent, so the blank borders of rotated CORONA
        frames disappear and only the real diagonal image strip shows.
        """
        uri = (
            "contextualWMSLegend=0&crs=EPSG:4326&dpiMode=7"
            "&format=image/png"
            f"&layers=corona:{layer_name}"
            "&styles=&tileMatrixSet=EPSG:4326&tilePixelRatio=0"
            f"&url={WMTS_BASE}"
        )
        rlayer = QgsRasterLayer(uri, f"CORONA {layer_name}", "wms")

        if not rlayer.isValid():
            QMessageBox.warning(
                self, "Layer error",
                f"Could not load WMTS layer for {layer_name}.\n"
                "Try opening the image in the browser instead.",
            )
            return

        self._set_white_transparent(rlayer)

        QgsProject.instance().addMapLayer(rlayer)
        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            f"Added CORONA {layer_name} to the map.",
            level=Qgis.Success,
            duration=4,
        )

    @staticmethod
    def _set_white_transparent(rlayer):
        """Render pure white (the no-data fill) transparent."""
        try:
            from qgis.core import QgsRasterTransparency
            tr = QgsRasterTransparency()
            px = QgsRasterTransparency.TransparentThreeValuePixel()
            px.red = 255.0
            px.green = 255.0
            px.blue = 255.0
            px.percentTransparent = 100.0
            tr.setTransparentThreeValuePixelList([px])

            renderer = rlayer.renderer()
            if renderer is not None:
                renderer.setRasterTransparency(tr)
            rlayer.triggerRepaint()
        except Exception as e:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(
                f"Could not set white transparency: {e}", "Corona CAST"
            )

    def _open_browser(self):
        webbrowser.open(self.web_url)
        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            "Opening Corona CAST Atlas in browser …",
            level=Qgis.Info,
            duration=3,
        )

    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_name(name):
        clean = name.replace("_", "-")
        if "Fore" in clean:
            camera = "Fore (forward camera)"
            base = clean.replace("Fore", "")
        elif "Aft" in clean:
            camera = "Aft (rear camera)"
            base = clean.replace("Aft", "")
        else:
            camera = "Unknown"
            base = clean
        parts = base.strip("-").split("-")
        mission = parts[0] if parts else "?"
        frame = parts[1] if len(parts) > 1 else "?"
        return mission, frame, camera
