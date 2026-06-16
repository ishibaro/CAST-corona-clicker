# -*- coding: utf-8 -*-
"""
cast_corona_clicker.py
Main plugin class.
  - Toolbar button to activate the click tool
  - Menu actions to download / update the cached CORONA index
  - Loads the capabilities cache into memory on first use
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import os
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication, QMessageBox
from qgis.core import Qgis
from qgis.utils import iface as qgis_iface

from . import capabilities as caps
from .clic_map_cast import CoronaMapTool
from .legacy_map_cast import LegacyMapTool
from .about_dialog import AboutDialog


class CoronaCastPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.map_tool = None
        self.legacy_tool = None
        self.action_click = None
        self.action_legacy = None
        self.action_update = None
        self.action_about = None
        self._layers = None      # cached {name: bbox} dict (lazy-loaded)

    def tr(self, message):
        return QCoreApplication.translate("CoronaCastPlugin", message)

    # ------------------------------------------------------------------ #
    #  GUI setup                                                           #
    # ------------------------------------------------------------------ #

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        legacy_icon_path = os.path.join(self.plugin_dir, "icon_legacy.png")
        self.map_tool = CoronaMapTool(self.iface.mapCanvas(), self)
        self.legacy_tool = LegacyMapTool(self.iface.mapCanvas())

        # --- Click & Explore (new) -----------------------------------
        self.action_click = QAction(
            QIcon(icon_path),
            self.tr("🛰 Click & Explore (find CORONA images)"),
            self.iface.mainWindow(),
        )
        self.action_click.setToolTip(
            self.tr(
                "Click the map to find which CORONA images cover that "
                "location, then load them into QGIS."
            )
        )
        self.action_click.setCheckable(True)
        self.action_click.triggered.connect(self.activate_tool)
        self.iface.addToolBarIcon(self.action_click)
        self.iface.addPluginToWebMenu(
            self.tr("&CAST Corona Clicker"), self.action_click
        )

        # --- Click & Go (legacy) -------------------------------------
        # Falls back to the main icon if no dedicated legacy icon exists.
        legacy_icon = (
            QIcon(legacy_icon_path)
            if os.path.exists(legacy_icon_path)
            else QIcon(icon_path)
        )
        self.action_legacy = QAction(
            legacy_icon,
            self.tr("🌐 Click & Go (open CAST Atlas in browser)"),
            self.iface.mainWindow(),
        )
        self.action_legacy.setToolTip(
            self.tr(
                "Original behaviour: click the map to open the Corona CAST "
                "Atlas in your browser at that location."
            )
        )
        self.action_legacy.setCheckable(True)
        self.action_legacy.triggered.connect(self.activate_legacy_tool)
        self.iface.addToolBarIcon(self.action_legacy)
        self.iface.addPluginToWebMenu(
            self.tr("&CAST Corona Clicker"), self.action_legacy
        )

        # Update-index action
        self.action_update = QAction(
            self.tr("Download / update CORONA index…"),
            self.iface.mainWindow(),
        )
        self.action_update.triggered.connect(self.update_index)
        self.iface.addPluginToWebMenu(
            self.tr("&CAST Corona Clicker"), self.action_update
        )

        # About action
        self.action_about = QAction(
            self.tr("About…"),
            self.iface.mainWindow(),
        )
        self.action_about.triggered.connect(self.show_about)
        self.iface.addPluginToWebMenu(
            self.tr("&CAST Corona Clicker"), self.action_about
        )

        # Uncheck buttons when another tool is selected
        self.map_tool.deactivated.connect(
            lambda: self.action_click.setChecked(False)
        )
        self.legacy_tool.deactivated.connect(
            lambda: self.action_legacy.setChecked(False)
        )

    def unload(self):
        actions = (
            self.action_click, self.action_legacy,
            self.action_update, self.action_about,
        )
        for a in actions:
            if a:
                self.iface.removePluginWebMenu(
                    self.tr("&CAST Corona Clicker"), a
                )
        for a in (self.action_click, self.action_legacy):
            if a:
                self.iface.removeToolBarIcon(a)
        if self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
        if self.legacy_tool:
            self.iface.mapCanvas().unsetMapTool(self.legacy_tool)

    # ------------------------------------------------------------------ #
    #  Capabilities cache                                                  #
    # ------------------------------------------------------------------ #

    def get_layers(self):
        """
        Return the cached {name: bbox} dict, loading it from disk on first
        use. Returns None if no cache exists yet.
        """
        if self._layers is not None:
            return self._layers

        if not caps.cache_exists(self.plugin_dir):
            return None

        try:
            text = caps.load_cached_capabilities(self.plugin_dir)
            self._layers = caps.parse_capabilities(text)
            return self._layers
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "🛰 Corona CAST",
                f"Failed to read cached index: {e}",
                level=Qgis.Critical,
                duration=6,
            )
            return None

    def update_index(self):
        """
        Download the latest GetCapabilities, compare with the cached one,
        and offer to save it.
        """
        has_cache = caps.cache_exists(self.plugin_dir)

        if has_cache:
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                "Update CORONA index",
                "A cached CORONA index already exists.\n\n"
                "Download the latest version from the CAST server and "
                "check whether it has changed?\n\n"
                "(The download is ~12 MB and may take a moment.)",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.iface.messageBar().pushMessage(
            "🛰 Corona CAST",
            "Downloading CORONA index from CAST server …",
            level=Qgis.Info,
            duration=3,
        )
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            new_text = caps.download_capabilities()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Download failed",
                f"Could not download the CORONA index:\n\n{e}\n\n"
                "The CAST server is sometimes slow or unavailable. "
                "Please try again later.",
            )
            return
        QApplication.restoreOverrideCursor()

        # Compare with cache if present
        changed = True
        if has_cache:
            try:
                old_text = caps.load_cached_capabilities(self.plugin_dir)
                changed = (old_text.strip() != new_text.strip())
            except Exception:
                changed = True

        new_layers = caps.parse_capabilities(new_text)
        n_new = len(new_layers)

        if has_cache and not changed:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Index up to date",
                f"The cached CORONA index is already up to date "
                f"({n_new} layers). Nothing to do.",
            )
            return

        # Offer to save
        msg = (
            f"Downloaded CORONA index with {n_new} layers.\n\n"
        )
        if has_cache:
            msg += "This differs from your cached version. "
        msg += "Save it as the new cached index?"

        reply = QMessageBox.question(
            self.iface.mainWindow(),
            "Save CORONA index",
            msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            caps.save_capabilities(self.plugin_dir, new_text)
            self._layers = new_layers   # refresh in-memory cache
            self.iface.messageBar().pushMessage(
                "🛰 Corona CAST",
                f"Saved CORONA index ({n_new} layers).",
                level=Qgis.Success,
                duration=4,
            )

    # ------------------------------------------------------------------ #
    #  About                                                               #
    # ------------------------------------------------------------------ #

    def show_about(self):
        dlg = AboutDialog(self.plugin_dir, self.iface.mainWindow())
        dlg.exec()

    # ------------------------------------------------------------------ #
    #  Tool activation                                                     #
    # ------------------------------------------------------------------ #

    def activate_tool(self):
        # Ensure index is available
        if self.get_layers() is None:
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                "CORONA index needed",
                "The CORONA image index hasn't been downloaded yet.\n\n"
                "Download it now from the CAST server?\n"
                "(~12 MB, one-time; cached for future use.)",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.update_index()
            if self.get_layers() is None:
                self.action_click.setChecked(False)
                return

        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.action_click.setChecked(True)

    def activate_legacy_tool(self):
        """Activate the original Click & Go tool (browser only, no index)."""
        self.iface.mapCanvas().setMapTool(self.legacy_tool)
        self.action_legacy.setChecked(True)
