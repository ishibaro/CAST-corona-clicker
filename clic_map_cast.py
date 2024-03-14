# -*- coding: utf-8 -*-
"""
ishiba March 2024
this tool extracts the coordinates of the canvas depending on CRS assigned and
opens Corona Cast webpage on the same coordinates
"""
import webbrowser
from qgis.gui import (QgsMapToolEmitPoint, QgsMessageBar)
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, Qgis
from qgis.utils import iface

class PrintClickedPoint(QgsMapToolEmitPoint):
    def __init__(self, canvas):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolEmitPoint.__init__(self, self.canvas)

    def canvasPressEvent( self, e ):
        point = self.toMapCoordinates(self.canvas.mouseLastXY())
        canvasCRS = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(canvasCRS, QgsCoordinateReferenceSystem("EPSG:3857"), QgsProject.instance())
        pt3857 = transform.transform(point.x(), point.y())
        northings = pt3857.y()
        eastings = pt3857.x()
        webbrowser.open('https://corona.cast.uark.edu/atlas#zoom=16&center={:.4f},{:.4f}'.format(eastings,northings))
        self.iface.messageBar().pushMessage("", "{} {:.8f},{:.8f} {}".format("Opening Corona CAST at this coordinates ", eastings,northings, "in external web browser"), level=Qgis.Info, duration=3)

canvas_clicked = PrintClickedPoint( iface.mapCanvas() )
iface.mapCanvas().setMapTool( canvas_clicked )