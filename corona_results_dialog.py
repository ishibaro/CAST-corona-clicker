# -*- coding: utf-8 -*-
"""
corona_results_dialog.py
Shows confirmed CORONA passes at the clicked location in a tree.
Each pass can be expanded to its individual frames.
Buttons let the user load a layer into QGIS or open the CAST atlas.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import webbrowser

from qgis.PyQt.QtCore import Qt
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

WMTS_BASE = "https://geoserve.cast.uark.edu/geoserver/gwc/service/wmts"


class CoronaResultsDialog(QDialog):

    def __init__(self, passes, layers, lat, lon, web_url, parent=None):
        super().__init__(parent)
        self.passes = passes          # confirmed pass names
        self.layers = layers          # full {name: bbox} dict
        self.lat = lat
        self.lon = lon
        self.web_url = web_url

        self.setWindowTitle("🛰 CORONA Imagery — CAST Atlas")
        self.setMinimumWidth(540)
        self.setMinimumHeight(420)
        self._build_ui()

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
                f"Expand a pass to see its frames.</i>"
            )
            info.setAlignment(Qt.AlignCenter)
            info.setWordWrap(True)
            root.addWidget(info)
            self._build_tree(root)
            self._build_action_buttons(root)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Open atlas in browser
        browser_btn = QPushButton("🌐  Open Corona CAST Atlas in browser")
        browser_btn.setToolTip(
            "Open the Corona CAST Atlas at this location.\n"
            "Supports CAST and lets you download original imagery."
        )
        browser_btn.clicked.connect(self._open_browser)
        root.addWidget(browser_btn)

        # Attribution
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
        self.tree.setColumnWidth(0, 320)
        self.tree.setAlternatingRowColors(True)

        for pass_name in self.passes:
            mission, frame, camera = self._parse_name(pass_name)
            top = QTreeWidgetItem([
                f"{pass_name}",
                f"Mission {mission} · {camera}",
            ])
            top.setData(0, Qt.UserRole, pass_name)
            top.setExpanded(False)

            # Add frame children
            frames = caps.frames_for_pass(self.layers, pass_name)
            if frames:
                for fr in frames:
                    child = QTreeWidgetItem([fr, "frame"])
                    child.setData(0, Qt.UserRole, fr)
                    top.addChild(child)
            else:
                placeholder = QTreeWidgetItem(["(no individual frames listed)", ""])
                top.addChild(placeholder)

            self.tree.addTopLevelItem(top)

        self.tree.itemSelectionChanged.connect(self._update_button_states)
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
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _update_button_states(self):
        self.add_btn.setEnabled(bool(self.tree.selectedItems()))

    def _add_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        for item in items:
            layer_name = item.data(0, Qt.UserRole)
            if layer_name:
                self._add_wmts_layer(layer_name)

    def _add_wmts_layer(self, layer_name):
        """Load a CORONA image as a WMTS layer via GeoWebCache."""
        uri = (
            "contextualWMSLegend=0&crs=EPSG:4326&dpiMode=7"
            "&format=image/jpeg"
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

        QgsProject.instance().addMapLayer(rlayer)
        iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            f"Added CORONA {layer_name} to the map.",
            level=Qgis.Success,
            duration=4,
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
