# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Tr55Dialog
                                 A QGIS plugin
 Transform QGIS data into WinTR-55 input data.
                             -------------------
        begin                : 2015-06-12
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Gkorgkolis Vasileios
        email                : vgkorgko@topo.auth.gr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import errno

from PyQt5 import QtGui, QtCore, uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.core import *
import processing
import math
#!from w55 import w55File
from datetime import date
from tr_55_dialog_base import Ui_Tr55DialogBase

#!FORM_CLASS, _ = uic.loadUiType(os.path.join(
    #!os.path.dirname(__file__), 'tr_55_dialog_base.ui'))


class Tr55Dialog(QDialog, Ui_Tr55DialogBase):
    def __init__(self, iface):
        """Constructor."""
        QDialog.__init__(self, None, QtCore.Qt.WindowStaysOnTopHint)
        #!super(Tr55Dialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.iface = iface
        # setup the gui
        self.setup_gui()

        # noinspection PyArgumentList
        self.plugin_builder_path = os.path.dirname(__file__)

        # set default directory for .w55 file and w55p folder in case another directory is not specified
        self.w55pDirectory = r'%USERPROFILE%\Desktop\W55p'
        self.filePath = r'%USERPROFILE%\Desktop\default.w55'
        # if Indicator = 0, default path is used
        self.pathIndicator = 0

        # connections
        QObject.connect(self.DirectoryButton, SIGNAL( "clicked()" ), self.writeFile)
        QObject.connect(self.WatershedsButton, SIGNAL( "clicked()" ), self.basins)
        self.button_box.accepted.connect(self.w55Connect)
        QObject.connect(self.noaaButton, SIGNAL( "clicked()" ), self.noaaConnect)



    def setup_gui(self):
        self.DEMCombo.clear()
        self.BasinsCombo.clear()
        self.CoverCombo.clear()
        self.HSGCombo.clear()
        self.ch_initLine.setText('5000000')
        self.ca_methodCombo.clear()
        self.coverList = []
        self.HSGList = []
        # set basins, land cover and HSG combos and labels inactive
        self.BasinsCombo.setEnabled(False)
        self.HSGCombo.setEnabled(False)
        self.CoverCombo.setEnabled(False)
        self.BasinsLabel.setEnabled(False)
        self.CoverTypeLabel.setEnabled(False)
        self.HSGLabel.setEnabled(False)
        # also disable the ok button
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        #! for now also disable ftp label, line and button...
        self.ftpLabel.setEnabled(False)
        self.ftpLine.setEnabled(False)
        self.noaaButton.setEnabled(False)

        # determine the catchment area algorithm options, populate the combobox and create a dictionary for use in basins
        ca_method = ['[0] Deterministic 8', '[1] Rho 8', '[2] Braunschweiger Reliefmodell', '[3] Deterministic Infinity',\
                        '[4] Multiple Flow Direction', '[5] Multiple Triangular F.D.']
        ca_input = [0, 1, 2, 3, 4, 5]
        self.ca_dict = dict(zip(ca_method, ca_input))
        self.ca_methodCombo.addItems(ca_method)

        # determine the layers for DEM
        for layer in self.iface.legendInterface().layers():
            if layer.type() == QgsMapLayer.RasterLayer:
                self.DEMCombo.addItem( layer.name(), layer )

    def basins(self):
        """Create watersheds and channel network"""
        # get the layer from DEM combo:
        DemCur = self.DEMCombo.currentIndex()
        self.DEM = self.DEMCombo.itemData(DemCur)
        # check indicator for use of default directory if custom directory not defined
        p = self.pathIndicator
        if p == 0:
            path = self.w55pDirectory
            try:
                os.makedirs(os.path.expandvars(path))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise

        """###### RUN PROCESSING ALGORITHMS #####"""
        # 1. Catchment area (SAGA): get method from combo, output loaded
        catchment_area = (os.path.expandvars(self.w55pDirectory)) + r'\catch.tif'
        ca = self.ca_methodCombo.currentText()
        processing.runalg('saga:catchmentarea', self.DEM, self.ca_dict[ca], catchment_area)
        processing.load(catchment_area)

        # 2. Channel network (SAGA): no layer loaded
        chnlntwrk = (os.path.expandvars(self.w55pDirectory)) + r'\ch_network.tif'
        chnlroute = (os.path.expandvars(self.w55pDirectory)) + r'\ch_direction.tif'
        shapes = (os.path.expandvars(self.w55pDirectory)) + r'\channel_network.shp'
        init_threshold = float(self.ch_initLine.text())
        processing.runalg('saga:channelnetwork', self.DEM, None, catchment_area, 2, init_threshold, None, None, None, None, chnlntwrk, chnlroute, shapes)
        processing.load(chnlroute)
        processing.load(shapes)
        #processing.load(chnlntwrk)

        # 3. Watershed basins (SAGA): output raster basins not loaded
        r_basins = (os.path.expandvars(self.w55pDirectory)) + r'\basins_rast.tif'
        processing.runalg('saga:watershedbasins', self.DEM, chnlntwrk, None, None, r_basins)
        #processing.load(r_basins)

        # 4. Vectorising grid classes (SAGA): output vector basins lacking area field, not loaded
        v_basins = (os.path.expandvars(self.w55pDirectory)) + r'\basins_noarea.shp'
        processing.runalg('saga:vectorisinggridclasses', r_basins, 1, None, None, v_basins)
        #processing.load(v_basins)

        # 5. Field calculator: add basins area field, not loaded
        a_basins = (os.path.expandvars(self.w55pDirectory)) + r'\basins_nostats.shp'
        processing.runalg('qgis:fieldcalculator', v_basins, 'Area', None, None, None, None, '$area', a_basins)
        #processing.load(a_basins)

        # 6. Field calculator: add channel network length (ft) field, not loaded
        #!! Just a remark. Existing length field produced by 'Channel network' algorithm has the same values as the pixels of
        #!! raster layer 'Flow width' produced by 'Flow width and specific catchment area' SAGA algorithm (not used here)
        streams_ft = (os.path.expandvars(self.w55pDirectory)) + r'\streams_ft.shp'
        processing.runalg('qgis:fieldcalculator', shapes, 'Length_ft', None, None, None, None, '$length*3.28084', streams_ft)
        #processing.load(streams_ft)

        # 7. Polygonize (raster to vector) (GDAL): create a polygon shapefile from raster channel network with each pixel's value as attribute (field DN)
        # not loaded
        str_plgnz = (os.path.expandvars(self.w55pDirectory)) + r'\str_plgnz.shp'
        processing.runalg('gdalogr:polygonize', chnlntwrk, None, str_plgnz)
        #processing.load(str_plgnz)

        # 8. Intersect (QGIS) the above polygonized streams with basins, to keep only streams within watershed. Not loaded.
        str_plgnz_int = (os.path.expandvars(self.w55pDirectory)) + r'\str_plgnz_int.shp'
        processing.runalg('qgis:intersection', str_plgnz, a_basins, str_plgnz_int)
        #processing.load(str_plgnz_int)

        # 9. Clip raster by mask layer (GDAL): mask the DEM with the above str_plgnz_int to create a raster layer "identical" to the
        # original raster streams layer (but retrained to the streams inside the basins). The streams' pixel values are now DEM's
        # corresponding pixels' elevation values. Needed below --> loaded...
        dem_clipper = (os.path.expandvars(self.w55pDirectory)) + r'\Dcl.tif'
        processing.runalg('gdalogr:cliprasterbymasklayer', self.DEM, str_plgnz_int, None, None, None, None, dem_clipper)
        processing.load(dem_clipper)

        # 10. Grid statistics for polygons (SAGA): compute min and max elevation values for each stream, add them as attribute fields
        # to the basins shapefile. Load it.
        basin_stats = (os.path.expandvars(self.w55pDirectory)) + r'\basins.shp'
        processing.runalg('saga:gridstatisticsforpolygons', dem_clipper, a_basins, False, True, True, True, False, True, True, False, None, basin_stats)
        processing.load(basin_stats)

        # 11. Clip vector by polygon (OGR): Just cut out the streams (lines) that are not inside the basins. Not loaded.
        streams_clip = (os.path.expandvars(self.w55pDirectory)) + r'\streams_cl.shp'
        processing.runalg('gdalogr:clipvectorsbypolygon', streams_ft, v_basins, None, streams_clip)
        #processing.load(streams_clip)

        # 12. Intersect (QGIS) the clipped streams with basin_stats to mix the corresponding attributes in a common attribute table.
        # Not loaded (contains split streams).
        str_bsn = (os.path.expandvars(self.w55pDirectory)) + r'\str_bsn.shp'
        processing.runalg('qgis:intersection', streams_clip, basin_stats, str_bsn)
        #processing.load(str_bsn)

        # 13. Field calculator: put in layer's length field the actual length. Not loaded.
        str_bsn_lngth = (os.path.expandvars(self.w55pDirectory)) + r'\str_bsn_lngth.shp'
        processing.runalg('qgis:fieldcalculator', str_bsn, 'Length', None, None, None, False, '$length', str_bsn_lngth)
        processing.load(str_bsn_lngth)

        # 14. Extract by attribute (QGIS): No 4 (Vectorising grid classes) produces polygons that include all the raster's pixels.
        # No 2 (Channel network) produces vector streams that connect pixel centroids. At the point where a basin's stream flows into
        # the neighbouring basin's stream, it has to extend into the other basin until it reaches the first pixel's centroid in order to
        # connect to the next stream. That fact creates a problem when intersecting (No 12), as it splits the streams in such occasions,
        # creating tiny stream lines with the length of either: half a pixel's side or half a pixel's diagonal (depending on the angle).
        # Find the half of a pixel's diagonal (channel network raster used):
        fileInfo = QtCore.QFileInfo(chnlntwrk)
        baseName = fileInfo.baseName()
        rlayer = QgsRasterLayer(chnlntwrk, baseName)
        pixel_x = QgsRasterLayer.rasterUnitsPerPixelX(rlayer)
        pixel_y = QgsRasterLayer.rasterUnitsPerPixelY(rlayer)
        pixel_dh = (math.sqrt(pixel_x**2 + pixel_y**2))/2
        # Run the extraction algorithm, load layer
        streams_tel = (os.path.expandvars(self.w55pDirectory)) + r'\streams.shp'
        processing.runalg('qgis:extractbyattribute', str_bsn_lngth, 'Length', 2, str(pixel_dh), streams_tel)
        processing.load(streams_tel)


        # reactivate basins, land cover and HSG combos and labels. And the OK button.
        self.BasinsCombo.setEnabled(True)
        self.HSGCombo.setEnabled(True)
        self.CoverCombo.setEnabled(True)
        self.BasinsLabel.setEnabled(True)
        self.CoverTypeLabel.setEnabled(True)
        self.HSGLabel.setEnabled(True)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

        # determine the layers for Basins
        for layer in self.iface.legendInterface().layers():
            if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() != QGis.Line:
                self.BasinsCombo.addItem( layer.name(), layer )
        # add the choices for Cover and Hydrologic Soil Group
        self.coverList = ['Smooth Impervious Areas: concrete, asphalt, gravel', 'Agricultural Lands: fallow',\
                    'Cultivated Soil: residue cover <20%', 'Cultivated Soil: residue cover >=20%', 'Grass: short grass prairie',\
                    'Grass: dense grass', 'Grass: Bermuda grass', 'Range (natural)', 'Woods: light underbrush', 'Woods: dense underbrush']
        self.HSGList = ['A', 'B', 'C', 'D']
        self.CoverCombo.addItems(self.coverList)
        self.HSGCombo.addItems(self.HSGList)


    def w55Connect(self):
        #!"""Connection to w55.py"""
        # get the layers from the 3 combos:
        # Watershed Basins
        BasinsCur = self.BasinsCombo.currentIndex()
        self.Basins = self.BasinsCombo.itemData(BasinsCur)
        # Cover Choices
        cover = str(self.CoverCombo.currentText())
        # HSG Choices
        hsg = str(self.HSGCombo.currentText())
        # connect to w55
        self.filePath = os.path.expandvars(self.filePath)
        #! w55File(self.Basins, cover, hsg, self.filePath)

        # last layer loaded (streams):
        layer = self.iface.activeLayer()
        basins_count = str(layer.featureCount())
        # create lists for basin name, basin area, stream length, stream slope
        b_area = []
        b_name = []
        s_length = []
        s_slope = []
        for i in layer.getFeatures():
            b_name.append(i['name'])
            b_area.append(i['area'])
            s_length.append(i['length'])                 # length in m. Units depend on the projection.
            s_slope.append((i['dcltif [ra']/i['length']))   # both in meters

        # create dictionaries for basin area, stream length, stream slope {"basin_name":value}
        area_dict = dict(zip(b_name,b_area))
        slength_dict = dict(zip(b_name,s_length))
        sslope_dict = dict(zip(b_name,s_slope))
        # HSG dictionary
        hsg_num_list = ['4', '6', '8', '10']
        hsg_dict = dict(zip(self.HSGList, hsg_num_list))
        # dictionaries for CN, Manning's n, Tc Manning's n and land use line number {"cover type":value}
        cn_a = ['98', '77', '67', '64', '49', '35', '30', '55', '45', '32']
        cn_b = ['98', '86', '78', '74', '69', '56', '58', '72', '66', '58']
        cn_c = ['98', '91', '85', '81', '79', '70', '71', '81', '77', '72']
        cn_d = ['98', '94', '89', '85', '84', '77', '78', '86', '83', '79']
        n_list = ['.011', '.05', '.06', '.17', '.15', '.24', '.41', '.13', '.40', '.80']
        line_n_list = ['8', '41', '46', '52', '81', '87', '84', '118', '94', '92']
        tc_n_list = ['0','1', '2', '3', '4', '5', '6', '9', '7', '8']
        tc_n_dict = dict(zip(self.coverList, tc_n_list))
        n_dict = dict(zip(self.coverList, n_list))
        line_dict = dict(zip(self.coverList, line_n_list))
        if hsg == 'A':
            cn_dict = dict(zip(self.coverList, cn_a))
        elif hsg == 'B':
            cn_dict = dict(zip(self.coverList, cn_b))
        elif hsg == 'C':
            cn_dict = dict(zip(self.coverList, cn_c))
        else:
            cn_dict = dict(zip(self.coverList, cn_d))


        """ .w55 file creation """
        f = open(self.filePath, 'w')
        f.write('"","","WinTR-55, Version 1",#' + date.today().isoformat() + '#,0,0\n')
        f.write('"Identification Data---"\n""\n""\n""\n"",""\n')
        f.write('" (km²)","<standard>"\n1,1,0\n89\n\n')
        f.write('"SubArea Data -----------"\n' + basins_count + '\n')
        #! outlet = '"          "' # Up to 10 alphanumeric characters.
        for c in b_name:    # according to the manual, basin name 1-10 char with at least one letter.
            area_km = str(round((area_dict[c] /1000000), 1))         # area in km**2, rounded to 1 decimal
            f.write('"b' + c + '","","r' + c + '",0\n')
            f.write('1,' + area_km + ',' + cn_dict[cover] + '\n')   # area in km**2
            f.write(line_dict[cover] + ',' + hsg_dict[hsg] + ',' + cn_dict[cover] + ','  + area_km +'\n')
            f.write('"","","",""\n"","","",""\n"","","",""\n"","","",""\n')
        f.write('\n"Storm Data--"\n"Type II",#TRUE#\n"User-provided custom storm data"\n')
        f.write('"2",     89\n"5",     114\n"10",    131\n"25",    147\n"50",      165\n"100",   183\n"1",     76\n\n')
        f.write('"Reach Data -------------"\n' +basins_count +'\n')
        for c in b_name:
            f.write('"r' + c + '","","",' +str(int(slength_dict[c])) + ',' + str(n_dict[cover]) + ',' + str(round((sslope_dict[c]),4)) + ',7,45\n')
            f.write('"","","","",""\n"","","","",""\n"","","","",""\n"","","","",""\n"","","","",""\n"","","","",""\n"","","","",""\n')
        f.write('\n"Structure Data ---------"\n0\n\n')
        f.write('"Tc Data -----------"\n')
        for c in b_name:
            f.write('""\n""\n')
            f.write('"3.5","' + str(int(slength_dict[c])) + '","' + str(round((sslope_dict[c]),4)) +'","' + str(tc_n_dict[cover]) + '","","","","","",""\n')
            f.write('"3.5","","","","","","","","",""\n"3.5","","","","","","","","",""\n"","","","","","","","","",""\n"","","","","","","","","",""\n')
        f.write('"Storms Run --------"\n0,0,0,0,0,0,0,\n')
        f.close

        # Start WinTR-55
        os.startfile(os.path.expandvars(self.filePath))

    def writeFile(self):
        fileName = QFileDialog.getSaveFileName(self, 'Save file',
                                        "", "w55 (*.w55);;All files (*)")
        directoryName = os.path.dirname(str(fileName))
        self.w55pDirectory = directoryName + '\W55p'
        fileName = os.path.splitext(str(fileName))[0]+'.w55'
        self.DirectoryLine.setText(fileName)
        self.filePath = fileName
        # Custom path determined ==> set pathIndicator to 1
        self.pathIndicator = 1
        # Folder creation for processing files in the same directory as the .w55 file
        # check if the folder exists, if not create it
        # folder name 'W55p'
        path = self.w55pDirectory
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

    def noaaConnect(self):
        pass
