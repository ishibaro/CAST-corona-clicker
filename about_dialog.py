# -*- coding: utf-8 -*-
"""
about_dialog.py
A tabbed About dialog: About / Help / Changelog.
Content is plain HTML so it's easy to edit.
Compatible with QGIS 3.16+ and QGIS 4.x
"""

import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTextBrowser,
    QLabel,
    QDialogButtonBox,
    QWidget,
)


# ------------------------------------------------------------------ #
#  HTML content — edit these freely                                   #
# ------------------------------------------------------------------ #

ABOUT_HTML = """
<h2>🛰 CAST Corona Clicker</h2>
<p><b>Version 2.0.0</b></p>

<p>Find and load declassified <b>CORONA spy satellite imagery
(1960&ndash;1972)</b> from the
<a href="https://corona.cast.uark.edu/">Corona CAST Atlas</a>
directly inside QGIS.</p>

<p>Click anywhere on the map to discover which CORONA satellite passes
cover that location &mdash; confirmed in real time against the imagery
server &mdash; then load any pass or frame as a layer, or open the
CAST Atlas in your browser.</p>

<p><b>Author:</b> Ishiba RO<br>
<b>Email:</b> ishiba.iro@gmail.com<br>
<b>Repository:</b>
<a href="https://github.com/ishibaro/CAST-corona-clicker">
github.com/ishibaro/CAST-corona-clicker</a></p>

<hr>

<p><small>version 2.0 iRO ©️ 2026
<br>version 0.1 created as part of the
<a href="https://eamena.org/">EAMENA</a> project
(University of Leicester / Durham University).</small></p>

<p><small>Imagery and services &copy; Center for Advanced Spatial
Technologies (CAST), University of Arkansas. Please cite:
Casana J., Cothren J. (2013) <i>The CORONA Atlas Project</i>,
SpringerBriefs in Archaeology.</small></p>
"""

HELP_HTML = """
<h2>How to use</h2>

<h3>1. First-time setup</h3>
<p>Before first use, download the CORONA image index (~12&nbsp;MB,
one time only):</p>
<p><b>Web menu &rarr; CAST Corona Clicker &rarr;
Download / update CORONA index&hellip;</b></p>
<p>This is cached on disk so you only need to do it once. The CORONA
archive almost never changes.</p>

<h3>2. Find imagery</h3>
<ol>
<li>Click the <b>🛰 toolbar button</b> to activate the tool.</li>
<li>Click anywhere on the QGIS canvas.</li>
<li>The plugin finds which satellite <b>passes</b> cover that point and
confirms real coverage against the server.</li>
<li>A dialog lists the confirmed passes. <b>Expand</b> a pass (click the
arrow) to see its individual frames.</li>
</ol>

<h3>3. Load or explore</h3>
<ul>
<li><b>🗺 Add selected to QGIS</b> &mdash; loads the chosen pass or frame
as a WMTS layer on your canvas.</li>
<li><b>🌐 Browser</b> &mdash; opens the Corona CAST Atlas at that location
so you can view and download the original imagery.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>CORONA mainly covers the Middle East, Central Asia, North Africa,
and parts of Europe and East Asia.</li>
<li>If no images appear, try the browser button to check coverage
visually on the CAST website.</li>
<li>"Fore" and "Aft" are the forward and rear cameras of each stereo
pass &mdash; both cover roughly the same ground from slightly different
angles.</li>
</ul>

<h3>Troubleshooting</h3>
<ul>
<li><b>"Capabilities not loaded yet"</b> &mdash; run the download/update
step from the menu first.</li>
<li><b>Slow or failed coverage check</b> &mdash; the CAST server is
occasionally overloaded. Wait a moment and try again.</li>
</ul>
"""

CHANGELOG_HTML = """
<h2>Changelog</h2>

<h3>Version 2.0.0</h3>
<p><i>Major rewrite.</i></p>
<ul>
<li><b>New:</b> Click now finds and confirms which CORONA images actually
cover the point, instead of just opening the browser.</li>
<li><b>New:</b> Results dialog with an expandable tree of passes and their
individual frames.</li>
<li><b>New:</b> Load any pass or frame directly into QGIS as a WMTS layer.</li>
<li><b>New:</b> On-disk cache of the CORONA index, with a menu option to
check for and download updates.</li>
<li><b>New:</b> Coverage confirmation uses WMS GetFeatureInfo against the
imagery cache, working around the offline footprints database.</li>
<li><b>New:</b> This About / Help / Changelog dialog.</li>
<li><b>Improved:</b> Background threading keeps QGIS responsive during
server queries.</li>
<li><b>Improved:</b> Compatible with both QGIS 3 and QGIS 4.</li>
<li><b>Fixed:</b> Click coordinate now uses the actual click position
rather than the last mouse position.</li>
</ul>

<h3>Version 0.1</h3>
<ul>
<li>Initial release: click the map to open the Corona CAST Atlas webpage
at the clicked coordinates.</li>
</ul>
"""


class AboutDialog(QDialog):

    def __init__(self, plugin_dir, parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.setWindowTitle("About — CAST Corona Clicker")
        self.setMinimumSize(560, 480)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ---- Optional header with icon -------------------------------
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            header = QHBoxLayout()
            icon_lbl = QLabel()
            pix = QPixmap(icon_path)
            if not pix.isNull():
                icon_lbl.setPixmap(
                    pix.scaled(48, 48, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
                )
            header.addWidget(icon_lbl)
            title = QLabel("<h2>CAST Corona Clicker</h2>")
            header.addWidget(title)
            header.addStretch()
            root.addLayout(header)

        # ---- Tabs -----------------------------------------------------
        tabs = QTabWidget()
        tabs.addTab(self._make_tab(ABOUT_HTML), "About")
        tabs.addTab(self._make_tab(HELP_HTML), "Help")
        tabs.addTab(self._make_tab(CHANGELOG_HTML), "Changelog")
        root.addWidget(tabs)

        # ---- Close button --------------------------------------------
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _make_tab(self, html):
        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(True)   # links open in system browser
        return browser
