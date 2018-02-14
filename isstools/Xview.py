import os
import re
import sys
import time
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import pkg_resources
from PyQt5 import QtGui, QtWidgets, QtCore, uic
from PyQt5.Qt import QSplashScreen, QObject
from PyQt5.QtCore import QSettings, QThread, pyqtSignal, QTimer, QDateTime
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar

from pathlib import Path

#import larch
#from larch_plugins.io import read_ascii
#from larch import Group as xafsgroup

#Libs for ZeroMQ communication
import socket
from PyQt5.QtCore import QThread
import zmq
import pickle
import pandas as pd

from matplotlib.figure import Figure

from isstools.xasdata import xasdata
from isstools.xasproject import xasproject

ui_path = pkg_resources.resource_filename('isstools', 'ui/Xview.ui')
gui_form = uic.loadUiType(ui_path)[0]  # Load the UI


class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self, hhm_pulses_per_deg, processing_sender=None, db=None, db_analysis=None, parent=None):

        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)

        self.hhm_pulses_per_deg = hhm_pulses_per_deg
        self.sender = processing_sender
        self.db = db
        self.db_analysis = db
        self.gen_parser = xasdata.XASdataGeneric(hhm_pulses_per_deg, db=db)

        self.xasproject = xasproject.XASProject()
        self.xasproject.datasets_changed.connect(self.addFilenameToXASProject)


        # pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.selectWorkingFolder)
        self.pushbuttonRefreshFolder.clicked.connect(self.getFileList)
        self.pushbutton_plot_bin.clicked.connect(self.plotBinnedData)
        self.comboBoxSortFilesBy.addItems(['Name', 'Time'])
        self.comboBoxSortFilesBy.currentIndexChanged.connect((self.getFileList))
        # file lists
        self.listFiles_bin.itemSelectionChanged.connect(self.selectBinnedDataFilesToPlot)
        self.listFiles_bin.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []


        self.binned_data = []
        self.gen = xasdata.XASdataGeneric(self.hhm_pulses_per_deg, db=None)

        self.last_num = ''
        self.last_den = ''


        # Persistent settings
        self.settings = QSettings('ISS Beamline', 'Xview')
        self.workingFolder = self.settings.value('WorkingFolder', defaultValue='/GPFS/xf08id/User Data', type=str)

        if self.workingFolder != '/GPFS/xf08id/User Data':
            self.labelWorkingFolder.setText(self.workingFolder)
            self.labelWorkingFolder.setToolTip(self.workingFolder)
            self.getFileList()

        # Setting up Preprocess tab:
        self.pushbutton_add_to_xasproject.clicked.connect(self.addDsToXASProject)
        self.listFiles_xasproject.itemSelectionChanged.connect(self.setLarchData)
        self.listFiles_xasproject.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.pushbutton_remove_xasproject.clicked.connect(self.removeFromXASProject)
        self.pushbutton_plotE_xasproject.clicked.connect(self.plotXASProjectInE)
        self.pushbutton_plotK_xasproject.clicked.connect(self.plotXASProjectInK)
        self.lineEdit_preedge_lo.textEdited.connect(self.updateDsParams)
        self.lineEdit_preedge_hi.textEdited.connect(self.updateDsParams)
        self.lineEdit_postedge_lo.textEdited.connect(self.updateDsParams)
        self.lineEdit_postedge_hi.textEdited.connect(self.updateDsParams)

        self.pushButton_preedge_lo_set.clicked.connect(self.setDsParamsFromGraph)
        self.pushButton_preedge_hi_set.clicked.connect(self.setDsParamsFromGraph)

    def addCanvas(self):
        self.figureBinned = Figure()
        self.figureBinned.set_facecolor(color='#FcF9F6')
        self.figureBinned.ax = self.figureBinned.add_subplot(111)
        self.canvas = FigureCanvas(self.figureBinned)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMaximumHeight(25)
        self.layout_plot_bin.addWidget(self.toolbar)
        self.layout_plot_bin.addWidget(self.canvas)
        self.canvas.draw()

        # XASProject Plot:
        self.figureXASProject = Figure()
        self.figureXASProject.set_facecolor(color='#FcF9F6')
        self.figureXASProject.ax = self.figureXASProject.add_subplot(111)
        self.canvasXASProject = FigureCanvas(self.figureXASProject)

        self.toolbar_XASProject = NavigationToolbar(self.canvasXASProject, self)
        self.toolbar_XASProject.setMaximumHeight(25)
        self.layout_plot_xasproject.addWidget(self.toolbar_XASProject)
        self.layout_plot_xasproject.addWidget(self.canvasXASProject)
        self.canvasXASProject.draw()
        #layout_plot_xasproject


    def selectWorkingFolder(self):
        self.workingFolder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open a folder", self.workingFolder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        self.settings.setValue('WorkingFolder', self.workingFolder)
        if len(self.workingFolder) > 50:
            self.labelWorkingFolder.setText(self.workingFolder[1:20] + '...' + self.WorkingFolder[-30:])
        else:
            self.labelWorkingFolder.setText(self.workingFolder)
        self.labelWorkingFolder.setToolTip(self.workingFolder)
        self.getFileList()

    def getFileList(self):
        if self.workingFolder:
            self.listFiles_bin.clear()

            files_bin = [f for f in os.listdir(self.workingFolder) if f.endswith('.dat')]

            if self.comboBoxSortFilesBy.currentText() == 'Name':
                files_bin.sort()
            elif self.comboBoxSortFilesBy.currentText() == 'Time':
                files_bin.sort(key=lambda x: os.path.getmtime('{}/{}'.format(self.workingFolder, x)))

                files_bin.reverse()
            self.listFiles_bin.addItems(files_bin)
    def selectBinnedDataFilesToPlot(self):
        header = xasdata.XASdataGeneric.read_header(None, '{}/{}'.format(self.workingFolder,
                                                                         self.listFiles_bin.currentItem().text()))
        self.keys = header[header.rfind('#'):][1:-1].split()
        self.keys.insert(0, '1')
        if 'timestamp' in self.keys:
            del self.keys[self.keys.index('timestamp')]

        if self.keys != self.last_keys:
            self.listBinnedDataNumerator.clear()
            self.listBinnedDataDenominator.clear()
            self.listBinnedDataNumerator.insertItems(0, self.keys)
            self.listBinnedDataDenominator.insertItems(0, self.keys)
            if self.last_num != '' and self.last_num <= len(self.keys) - 1:
                self.listBinnedDataNumerator.setCurrentRow(self.last_num)
            if self.last_den != '' and self.last_den <= len(self.keys) - 1:
                self.listBinnedDataDenominator.setCurrentRow(self.last_den)



    def plotBinnedData(self):
        selected_items = (self.listFiles_bin.selectedItems())
        self.figureBinned.ax.clear()
        self.toolbar._views.clear()
        self.toolbar._positions.clear()
        self.toolbar._update_view()
        self.canvas.draw_idle()

        if self.listBinnedDataNumerator.currentRow() == -1 or self.listBinnedDataDenominator.currentRow() == -1:
            self.statusBar().showMessage('Please select numerator and denominator')
            return

        self.last_num = self.listBinnedDataNumerator.currentRow()
        self.last_den = self.listBinnedDataDenominator.currentRow()

        if 'En. (eV)' in self.keys:
            energy_key = 'En. (eV)'
        elif 'energy' in self.keys:
            energy_key = 'energy'

        handles = []
        for i in selected_items:
            self.gen.loadInterpFile('{}/{}'.format(self.workingFolder, i.text()))
            df = pd.DataFrame({k: v[:, 1] for k, v in self.gen.interp_arrays.items()}).sort_values(energy_key)
            division = df[self.listBinnedDataNumerator.currentItem().text()] \
                       / df[self.listBinnedDataDenominator.currentItem().text()]
            if self.checkBox_log_bin.checkState():
                division = np.log(division)
            if self.checkBox_inv_bin.checkState():
                division = -division

            self.figureBinned.ax.plot(df[energy_key], division)
            self.figureBinned.ax.set_xlabel('Energy (eV)')
            self.figureBinned.ax.set_ylabel('{} / {}'.format(self.listBinnedDataNumerator.currentItem().text(),
                                                             self.listBinnedDataDenominator.currentItem().text()))
            last_trace = self.figureBinned.ax.get_lines()[len(self.figureBinned.ax.get_lines()) - 1]
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            handles.append(patch)

        self.figureBinned.ax.legend(handles=handles)
        self.figureBinned.tight_layout()
        self.canvas.draw_idle()


    # here we begin to work on the second pre-processing tab
    def updateDsParams(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        selection = self.listFiles_xasproject.selectedIndexes()

        if selection is not None:
            index=selection[0].row()
            ds = self.xasproject[index]
            sender_dict = {
                'lineEdit_preedge_lo': 'pre1',
                'lineEdit_preedge_hi': 'pre2',
                'lineEdit_postedge_lo': 'norm1',
                'lineEdit_postedge_hi': 'norm2',
            }

            try:
                self.statusBar().showMessage(sender_object)
                setattr(ds, sender_dict[sender_object], float(getattr(self, sender_object).text()))

            except:
                self.statusBar().showMessage('Use numbers only')

    def setDsParamsFromGraph(self):
        sender = QObject()
        self.sender_object = sender.sender().objectName()
        self.statusBar().showMessage('Click on graph or press Esc')
        self.cid = self.canvasXASProject.mpl_connect('button_press_event',  self.mouse_press_event)
        print(f'cid={self.cid}')

    def _disconnect_cid(self):
        if hasattr(self, 'cid'):
            print(f'cid {self.cid} removed')
            self.canvasXASProject.mpl_disconnect(self.cid)
            delattr(self, 'cid')
        else:
            print(f'cid is not installed')

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self._disconnect_cid()

    def mouse_press_event(self, event):
        print(event.button, event.x, event.y, event.xdata, event.ydata)
        print(self.sender_object)
        sender_dict = {
            'pushButton_preedge_lo_set': 'lineEdit_preedge_lo',
            'pushButton_preedge_hi_set': 'lineEdit_preedge_hi',
            'pushButton_postedge_lo_set': 'lineEdit_postedge_lo',
            'pushButton_postedge_hi_set': 'lineEdit_postedge_hi',
        }
        lineEdit=getattr(self, sender_dict[self.sender_object])
        lineEdit.setText(str(event.xdata))
        self._disconnect_cid()


    def setLarchData(self):
        if self.listFiles_xasproject.selectedIndexes():
            index=self.listFiles_xasproject.selectedIndexes()[0]
            ds = self.xasproject[index.row()]
            self.lineEdit_e0.setText('{:.1f}'.format(ds.e0))
            self.lineEdit_preedge_lo.setText('{:.1f}'.format(ds.pre1))
            self.lineEdit_preedge_hi.setText('{:.1f}'.format(ds.pre2))
            self.lineEdit_postedge_lo.setText('{:.1f}'.format(ds.norm1))
            self.lineEdit_postedge_hi.setText('{:.1f}'.format(ds.norm2))
            # Make the first selected line bold, and reset bold font for other selections
            font = QtGui.QFont()
            font.setBold(False)
            for i in range(self.listFiles_xasproject.count()):
                self.listFiles_xasproject.item(i).setFont(font)
            font.setBold(True)
            self.listFiles_xasproject.item(index.row()).setFont(font)

    def addDsToXASProject(self):
        if self.listBinnedDataNumerator.currentRow() != -1 and self.listBinnedDataDenominator.currentRow() != -1:
            for item in self.listFiles_bin.selectedItems():
                filepath = str(Path(self.workingFolder) / Path(item.text()))
                header = self.gen_parser.read_header(filepath)
                uid = header[header.find('real_uid:')+10:header.find('\n', header.find('real_uid:'))]
                md = self.db[uid]['start']
                ds = xasproject.XASDataSet()
                self.gen_parser.data_manager.loadBinFile(filepath)
                df = self.gen_parser.data_manager.binned_df
                df = df.sort_values('energy')
                num_key = self.listBinnedDataNumerator.currentItem().text()
                den_key = self.listBinnedDataDenominator.currentItem().text()
                mu = df[num_key] / df[den_key]

                if self.checkBox_log_bin.checkState():
                    mu = np.log(mu)
                if self.checkBox_inv_bin.checkState():
                    mu = -mu


                ds.md = md
                ds.larch.mu = mu
                ds.larch.energy = df['energy']
                ds.filename = filepath
                ds.subtract_background()
                self.xasproject.append(ds)
                self.statusBar().showMessage('Scans added to the project successfully')
        else:
            self.statusBar().showMessage('Select numerator and denominator columns')


    def addFilenameToXASProject(self, datasets):
        self.listFiles_xasproject.clear()
        for ds in datasets:
            fn = ds.filename
            fn = fn[fn.rfind('/') + 1:]
            self.listFiles_xasproject.addItem(fn)

    def removeFromXASProject(self):
        print(self.listFiles_xasproject.selectedIndexes())
        for index in self.listFiles_xasproject.selectedIndexes()[::-1]: #[::-1] to remove using indexes from last to first
            self.xasproject.removeDatasetIndex(index.row())

    def plotXASProjectInE(self):
        self.figureXASProject.ax.clear()
        self.toolbar_XASProject._views.clear()
        self.toolbar_XASProject._positions.clear()
        self.toolbar_XASProject._update_view()
        self.canvasXASProject.draw_idle()

        for index in self.listFiles_xasproject.selectedIndexes():
            ds = self.xasproject[index.row()]
            ds.subtract_background_force()
        #for ds in self.xasproject:

            if self.radioButton_mu_xasproject.isChecked():
                data = ds.mu
                if self.checkBox_preedge_show.checkState():
                    self.figureXASProject.ax.plot(ds.energy, ds.pre_edge)
                if self.checkBox_postedge_show.checkState():
                    self.figureXASProject.ax.plot(ds.energy, ds.post_edge)
            elif self.radioButton_norm_xasproject.isChecked():
                if self.checkBox_norm_flat_xasproject.checkState():
                    indx_e0 = np.abs(ds.energy-ds.e0).argmin()
                    flattening_bkg = ds.post_edge - ds.pre_edge
                    norm_factor = flattening_bkg[indx_e0]

                    flattening_bkg[indx_e0::] = flattening_bkg[indx_e0::] - norm_factor
                    mu_flattened = ds.mu.values.flatten()-ds.pre_edge
                    mu_flattened[indx_e0::] = mu_flattened[indx_e0::] - flattening_bkg[indx_e0::]
                    mu_flattened[indx_e0::] = mu_flattened[indx_e0::] / norm_factor
                    data = mu_flattened
                else:
                    data = ds.norm
            self.figureXASProject.ax.plot(ds.energy, data)
        self.canvasXASProject.draw_idle()

    def plotXASProjectInK(self):
        self.figureXASProject.ax.clear()
        self.toolbar_XASProject._views.clear()
        self.toolbar_XASProject._positions.clear()
        self.toolbar_XASProject._update_view()
        self.canvasXASProject.draw_idle()

        for index in self.listFiles_xasproject.selectedIndexes():
            ds = self.xasproject[index.row()]
            ds.extract_chi()
            if self.radioButton_k_weight_1.isChecked():
                data=ds.k*ds.chi
            elif self.radioButton_k_weight_2.isChecked():
                data = ds.k *ds.k * ds.chi
            elif self.radioButton_k_weight_3.isChecked():
                data = ds.k * ds.k * ds. k* ds.chi

            self.figureXASProject.ax.plot(ds.k, data)

        self.canvasXASProject.draw_idle()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())
