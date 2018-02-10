import os
import re
import sys
import time
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import pkg_resources
from PyQt5 import QtGui, QtWidgets, QtCore, uic
from PyQt5.Qt import QSplashScreen
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

        # Activating ZeroMQ Receiving Socket
        # self.context = zmq.Context()
        # self.subscriber = self.context.socket(zmq.SUB)
        # self.subscriber.connect("tcp://xf08id-srv1:5562")
        # self.hostname_filter = socket.gethostname()
        # self.subscriber.setsockopt_string(zmq.SUBSCRIBE, self.hostname_filter)
        # self.receiving_thread = ReceivingThread(self)

        self.xasproject = xasproject.XASProject()
        self.xasproject.datasets_changed.connect(self.addFilenameToXASProject)


        # pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.selectWorkingFolder)
        self.pushbuttonRefreshFolder.clicked.connect(self.getFileList)
        self.pushbutton_plot_bin.clicked.connect(self.plotBinnedData)
        self.pushbutton_plot_raw.clicked.connect(self.plotRawData)
        self.push_bin.clicked.connect(self.bin_data)
        self.push_save_bin.clicked.connect(self.save_binned_data)

        # comboboxes
        # self.comboBoxFileType.addItems( ['Raw (*.txt)', 'Binned (*.dat)','All'])
        # self.comboBoxFileType.currentIndexChanged.connect((self.getFileList))
        self.comboBoxSortFilesBy.addItems(['Name', 'Time'])
        self.comboBoxSortFilesBy.currentIndexChanged.connect((self.getFileList))
        # file lists
        self.listFiles_bin.itemSelectionChanged.connect(self.selectBinnedDataFilesToPlot)
        self.listFiles_bin.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listFiles_raw.itemSelectionChanged.connect(self.selectRawDataFilesToPlot)
        self.listFiles_raw.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []
        self.keys_raw = []
        self.last_keys_raw = []
        self.binned_data = []

        # mds = MDS({'host': 'xf08id-ca1.cs.nsls2.local', 'port': 7770,'timezone': 'US/Eastern'})
        # self.db = Broker(mds, FileStore({'host':'xf08id-ca1.cs.nsls2.local', 'port': 27017, 'database':'filestore'}))


        # Create generic parser
        self.gen = xasdata.XASdataGeneric(self.hhm_pulses_per_deg, db=None)

        self.last_num = ''
        self.last_den = ''
        self.last_num_raw = ''
        self.last_den_raw = ''

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
        self.lineEdit_preedge_lo.textChanged.connect(self.update_ds_preedge_lo)
        self.lineEdit_preedge_hi.textChanged.connect(self.update_ds_preedge_hi)

    def update_ds_preedge_lo(self):
        index = self.listFiles_xasproject.selectedIndexes()[0].row()
        ds = self.xasproject[index]
        try:
            ds.pre1 = float(self.lineEdit_preedge_lo.text())
        except:
            pass

    def update_ds_preedge_hi(self):
        index = self.listFiles_xasproject.selectedIndexes()[0].row()
        ds = self.xasproject[index]
        try:
            ds.pre2 = float(self.lineEdit_preedge_hi.text())
        except:
            pass


    def setLarchData(self):
        if self.listFiles_xasproject.selectedIndexes():
            index=self.listFiles_xasproject.selectedIndexes()[0]
            ds = self.xasproject[index.row()]
            self.lineEdit_e0.setText('{:.1f}'.format(ds.e0))
            self.lineEdit_preedge_lo.setText('{:.1f}'.format(ds.pre1))
            self.lineEdit_preedge_hi.setText('{:.1f}'.format(ds.pre2))
            self.lineEdit_postedge_lo.setText('{:.1f}'.format(ds.norm1))
            self.lineEdit_postedge_hi.setText('{:.1f}'.format(ds.norm2))
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

        else:
            raise IndexError('Select Numerator and Denominator')

        print('Scans added to the project successfully')

    def addFilenameToXASProject(self, datasets):
        self.listFiles_xasproject.clear()
        for ds in datasets:
            fn = ds.filename
            fn = fn[fn.rfind('/') + 1:]
            self.listFiles_xasproject.addItem(fn)

    def removeFromXASProject(self):
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
                    self.figureXASProject.ax.plot(larch.energy, larch.pre_edge)
                if self.checkBox_postedge_show.checkState():
                    self.figureXASProject.ax.plot(larch.energy, larch.post_edge)
            elif self.radioButton_norm_xasproject.isChecked():
                if self.checkBox_norm_flat_xasproject.checkState():
                    indx_e0 = np.abs(larch.energy-larch.e0).argmin()
                    flattening_bkg = larch.post_edge - larch.pre_edge
                    norm_factor = flattening_bkg[indx_e0]

                    flattening_bkg[indx_e0::] = flattening_bkg[indx_e0::] - norm_factor
                    mu_flattened = larch.mu.values.flatten()-larch.pre_edge
                    mu_flattened[indx_e0::] = mu_flattened[indx_e0::] - flattening_bkg[indx_e0::]
                    mu_flattened[indx_e0::] = mu_flattened[indx_e0::] / norm_factor
                    data = mu_flattened
                else:
                    data = larch.norm
            self.figureXASProject.ax.plot(larch.energy, data)
        self.canvasXASProject.draw_idle()

    def addCanvas(self):
        self.figureBinned = Figure()
        self.figureBinned.set_facecolor(color='#FcF9F6')
        self.figureBinned.ax = self.figureBinned.add_subplot(111)
        self.figureBinned.ax = self.figureBinned.add_subplot(111)
        self.canvas = FigureCanvas(self.figureBinned)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMaximumHeight(25)
        self.layout_plot_bin.addWidget(self.toolbar)
        self.layout_plot_bin.addWidget(self.canvas)
        self.canvas.draw()

        self.figureRaw = Figure()
        self.figureRaw.set_facecolor(color='#FcF9F6')
        self.figureRaw.ax = self.figureRaw.add_subplot(111)
        self.canvasRaw = FigureCanvas(self.figureRaw)

        self.toolbar_raw = NavigationToolbar(self.canvasRaw, self)
        self.toolbar_raw.setMaximumHeight(25)
        self.layout_plot_raw.addWidget(self.toolbar_raw)
        self.layout_plot_raw.addWidget(self.canvasRaw)
        self.canvasRaw.draw()


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
            self.listFiles_raw.clear()
            self.listFiles_bin.clear()
            files_raw = [f for f in os.listdir(self.workingFolder) if f.endswith('.txt')]
            files_bin = [f for f in os.listdir(self.workingFolder) if f.endswith('.dat')]

            if self.comboBoxSortFilesBy.currentText() == 'Name':
                files_raw.sort()
                files_bin.sort()
            elif self.comboBoxSortFilesBy.currentText() == 'Time':
                files_raw.sort(key=lambda x: os.path.getmtime('{}/{}'.format(self.workingFolder, x)))
                files_bin.sort(key=lambda x: os.path.getmtime('{}/{}'.format(self.workingFolder, x)))
                files_raw.reverse()
                files_bin.reverse()
            self.listFiles_raw.addItems(files_raw)
            self.listFiles_bin.addItems(files_bin)

    def selectRawDataFilesToPlot(self):
        header = xasdata.XASdataGeneric.read_header(None, '{}/{}'.format(self.workingFolder,
                                                                         self.listFiles_raw.currentItem().text()))
        self.keys_raw = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        self.keys_raw.insert(0, '1')

        if 'timestamp' in self.keys:
            del self.keys[self.keys.index('timestamp')]

        if self.keys_raw != self.last_keys_raw:
            self.listRawDataNumerator.clear()
            self.listRawDataDenominator.clear()
            self.listRawDataNumerator.insertItems(0, self.keys_raw)
            self.listRawDataDenominator.insertItems(0, self.keys_raw)

            if self.last_num_raw != '' and self.last_num_raw <= len(self.keys_raw) - 1:
                self.listRawDataNumerator.setCurrentRow(self.last_num_raw)
            if self.last_den_raw != '' and self.last_den_raw <= len(self.keys_raw) - 1:
                self.listRawDataDenominator.setCurrentRow(self.last_den_raw)

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

    def plotRawData(self):
        self.push_save_bin.setEnabled(False)
        selected_items = (self.listFiles_raw.selectedItems())
        self.figureRaw.ax.clear()
        self.toolbar_raw._views.clear()
        self.toolbar_raw._positions.clear()
        self.toolbar_raw._update_view()
        self.canvasRaw.draw_idle()

        if self.listRawDataNumerator.currentRow() == -1 or self.listRawDataDenominator.currentRow() == -1:
            self.show_info_message('Error!', '1 Please, select numerator and denominator')
            return

        self.last_num_raw = self.listRawDataNumerator.currentRow()
        self.last_den_raw = self.listRawDataDenominator.currentRow()

        if 'En. (eV)' in self.keys_raw:
            energy_key = 'En. (eV)'
        elif 'energy' in self.keys_raw:
            energy_key = 'energy'

        self.handles_raw = []
        for i in selected_items:
            self.gen.loadInterpFile('{}/{}'.format(self.workingFolder, i.text()))

            df = pd.DataFrame({k: v[:, 1] for k, v in self.gen.interp_arrays.items()}).sort_values(energy_key)

            division = df[self.listRawDataNumerator.currentItem().text()] \
                       / df[self.listRawDataDenominator.currentItem().text()]
            if self.checkBox_log_raw.checkState():
                division = np.log(division)
            if self.checkBox_inv_raw.checkState():
                division = -division

            self.figureRaw.ax.plot(df[energy_key], division)
            self.figureRaw.ax.set_xlabel('Energy (eV)')
            self.figureRaw.ax.set_ylabel('{} / {}'.format(self.listRawDataNumerator.currentItem().text(),
                                                          self.listRawDataDenominator.currentItem().text()))
            last_trace = self.figureRaw.ax.get_lines()[len(self.figureRaw.ax.get_lines()) - 1]
            last_trace.type = 'raw'
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            self.handles_raw.append(patch)

        self.figureRaw.ax.legend(handles=self.handles_raw)
        self.figureRaw.tight_layout()
        self.canvasRaw.draw_idle()

    def plotBinnedData(self):
        selected_items = (self.listFiles_bin.selectedItems())
        self.figureBinned.ax.clear()
        self.toolbar._views.clear()
        self.toolbar._positions.clear()
        self.toolbar._update_view()
        self.canvas.draw_idle()

        if self.listBinnedDataNumerator.currentRow() == -1 or self.listBinnedDataDenominator.currentRow() == -1:
            self.show_info_message('Error!', 'Please, select numerator and denominator')
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

    def bin_data(self):
        for index, trace in enumerate(self.figureRaw.ax.get_lines()):
            if trace.type == 'binned':
                trace.remove()
                del self.handles_raw[-1]

        selected_items = [f.text() for f in self.listFiles_raw.selectedItems()]

        for index, f in enumerate(selected_items):
            filepath = '{}/{}'.format(self.workingFolder, f)
            ''' Eli's comment - exception handling - if user types a character in one of the field the float() will fail
                an expensive was of doing it is to have a function for each field which, as user typess the value, checks if it's 
                indeed a number'''
            # for  now I suggest try except
            e0 = float(self.edit_E0.text())
            edge_start = float(self.edit_edge_start.text())
            edge_end = float(self.edit_edge_end.text())
            preedge_spacing = float(self.edit_preedge_spacing.text())
            xanes_spacing = float(self.edit_xanes_spacing.text())
            exafs_spacing = float(self.edit_exafs_spacing.text())
            filepath = '{}/{}'.format(self.workingFolder, f)
            params = (self.hhm_pulses_per_deg, e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_spacing, filepath)

            process_thread_bin = process_bin_thread(*params, index=index)
            process_thread_bin.finished_bin.connect(self.plot_binned_data)
            process_thread_bin.start()

    def plot_binned_data(self, binned):
        result = binned[self.listRawDataNumerator.currentItem().text()] / binned[
            self.listRawDataDenominator.currentItem().text()]
        ylabel = '{} / {}'.format(self.listRawDataNumerator.currentItem().text(),
                                  self.listRawDataDenominator.currentItem().text())

        if self.checkBox_log_raw.isChecked():
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
        ylabel = 'Binned {}'.format(ylabel)
        xlabel = binned['energy_string']

        if self.checkBox_inv_raw.isChecked():
            result = -result

        self.figureRaw.ax.plot(binned[xlabel][:len(result)], result)
        last_trace = self.figureRaw.ax.get_lines()[len(self.figureRaw.ax.get_lines()) - 1]
        last_trace.type = 'binned'
        filepath = binned['filepath'][binned['filepath'].rfind('/') + 1:] + ' (binned)'
        patch = mpatches.Patch(color=last_trace.get_color(), label=filepath)
        self.handles_raw.append(patch)

        self.figureRaw.ax.legend(handles=self.handles_raw)
        self.figureRaw.tight_layout()
        self.canvasRaw.draw_idle()

        self.binned_data.append(binned)

        self.push_save_bin.setEnabled(True)

    def save_binned_data(self):
        for binned in self.binned_data:
            self.gen.data_manager.binned_arrays = binned
            self.gen.data_manager.export_dat(binned['filepath'])

    def show_info_message(self, title, message):
        QtWidgets.QMessageBox.question(self,
                                       title,
                                       message,
                                       QtWidgets.QMessageBox.Ok)


class process_bin_thread(QThread):
    finished_bin = pyqtSignal(dict)

    def __init__(self, hhm_pulses_per_deg, e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_spacing, filepath, index=1):
        QThread.__init__(self)
        self.gen_parser = xasdata.XASdataGeneric(hhm_pulses_per_deg, db=None)

        self.e0 = e0
        self.edge_start = edge_start
        self.edge_end = edge_end
        self.preedge_spacing = preedge_spacing
        self.xanes_spacing = xanes_spacing
        self.exafs_spacing = exafs_spacing
        self.filepath = filepath

        self.index = index

    def __del__(self):
        self.wait()

    def run(self):
        print('[Binning Thread {}] Starting...'.format(self.index))

        self.gen_parser.loadInterpFile(self.filepath)
        binned = self.gen_parser.bin(self.e0,
                                     self.e0 + self.edge_start,
                                     self.e0 + self.edge_end,
                                     self.preedge_spacing,
                                     self.xanes_spacing,
                                     self.exafs_spacing)

        energy_string = self.gen_parser.get_energy_string()
        binned['energy_string'] = energy_string
        binned['filepath'] = self.filepath

        print('[Binning Thread {}] Finished'.format(self.index))
        self.finished_bin.emit(binned)


class ReceivingThread(QThread):
    received_interp_data = QtCore.pyqtSignal(object)
    received_bin_data = QtCore.pyqtSignal(object)
    received_req_interp_data = QtCore.pyqtSignal(object)
    def __init__(self, gui):
        QThread.__init__(self)
        self.setParent(gui)

    def run(self):
        while True:
            message = self.parent().subscriber.recv()
            message = message[len(self.parent().hostname_filter):]
            data = pickle.loads(message)

            if 'data' in data['processing_ret']:
                data['processing_ret']['data'] = pd.read_msgpack(data['processing_ret']['data'])

            if data['type'] == 'spectroscopy':
                if data['processing_ret']['type'] == 'interpolate':
                    self.received_interp_data.emit(data)
                if data['processing_ret']['type'] == 'bin':
                    self.received_bin_data.emit(data)
                if data['processing_ret']['type'] == 'request_interpolated_data':
                    self.received_req_interp_data.emit(data)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())
