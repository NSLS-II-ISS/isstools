import sys, os
import numpy as np
from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import QSettings, QThread, pyqtSignal
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import  FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import matplotlib.patches as mpatches
import pkg_resources
from isstools.xasdata import xasdata
import re
import pandas as pd

ui_path = pkg_resources.resource_filename('isstools', 'ui/Xview.ui')
gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        #pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.selectWorkingFolder)
        self.pushbuttonRefreshFolder.clicked.connect(self.getFileList)
        self.pushbutton_plot_bin.clicked.connect(self.plot_bin)
        self.pushbutton_plot_raw.clicked.connect(self.plot_raw)
        self.push_bin.clicked.connect(self.bin_data)
        self.push_save_bin.clicked.connect(self.save_binned_data)
        #comboboxes
        #self.comboBoxFileType.addItems( ['Raw (*.txt)', 'Binned (*.dat)','All'])
        #self.comboBoxFileType.currentIndexChanged.connect((self.getFileList))
        self.comboBoxSortFilesBy.addItems(['Name', 'Time'])
        self.comboBoxSortFilesBy.currentIndexChanged.connect((self.getFileList))
        #file lists
        self.listFiles_bin.itemSelectionChanged.connect(self.select_files_bin)
        self.listFiles_bin.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listFiles_raw.itemSelectionChanged.connect(self.select_files_raw)
        self.listFiles_raw.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []
        self.keys_raw = []
        self.last_keys_raw = []
        self.binned_data = []


        #mds = MDS({'host': 'xf08id-ca1.cs.nsls2.local', 'port': 7770,'timezone': 'US/Eastern'})
        #self.db = Broker(mds, FileStore({'host':'xf08id-ca1.cs.nsls2.local', 'port': 27017, 'database':'filestore'}))


        # Create generic parser
        self.gen = xasdata.XASdataGeneric(db = None)

        self.last_num = ''
        self.last_den = ''
        self.last_num_raw = ''
        self.last_den_raw = ''

        # Persistent settings
        self.settings = QSettings('ISS Beamline', 'Xview')
        self.workingFolder = self.settings.value('WorkingFolder', defaultValue = '/GPFS/xf08id/User Data', type = str)


        if self.workingFolder != '/GPFS/xf08id/User Data':
            self.labelWorkingFolder.setText(self.workingFolder)
            self.labelWorkingFolder.setToolTip(self.workingFolder)
            self.getFileList()


    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.figure.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMaximumHeight(25)
        self.layout_plot_bin.addWidget(self.toolbar)
        self.layout_plot_bin.addWidget(self.canvas)
        self.canvas.draw()


        self.figure_raw = Figure()
        self.figure_raw.set_facecolor(color='#FcF9F6')
        self.figure_raw.ax = self.figure_raw.add_subplot(111)
        self.canvas_raw = FigureCanvas(self.figure_raw)

        self.toolbar_raw = NavigationToolbar(self.canvas_raw, self)
        self.toolbar_raw.setMaximumHeight(25)
        self.layout_plot_raw.addWidget(self.toolbar_raw)
        self.layout_plot_raw.addWidget(self.canvas_raw)
        self.canvas_raw.draw()


    def selectWorkingFolder(self):
        self.workingFolder = QtWidgets.QFileDialog.getExistingDirectory(self, "Open a folder", self.workingFolder, QtWidgets.QFileDialog.ShowDirsOnly)
        self.settings.setValue('WorkingFolder', self.workingFolder)
        if len(self.workingFolder)>50:
            self.labelWorkingFolder.setText(self.workingFolder [1:20] + '...' + self.WorkingFolder[-30:])
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

    def select_files_raw(self):
        header = xasdata.XASdataGeneric.read_header(None, '{}/{}'.format(self.workingFolder,
                                                                         self.listFiles_raw.currentItem().text()))
        self.keys_raw = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        self.keys_raw.insert(0, '1')

        if 'timestamp' in self.keys:
            del self.keys[self.keys.index('timestamp')]

        if self.keys_raw != self.last_keys_raw:
            self.listWidget_num_raw.clear()
            self.listWidget_den_raw.clear()
            self.listWidget_num_raw.insertItems(0, self.keys_raw)
            self.listWidget_den_raw.insertItems(0, self.keys_raw)

            if self.last_num_raw != '' and self.last_num_raw <= len(self.keys_raw) - 1:
                self.listWidget_num_raw.setCurrentRow(self.last_num_raw)
            if self.last_den_raw != '' and self.last_den_raw <= len(self.keys_raw) - 1:
                self.listWidget_den_raw.setCurrentRow(self.last_den_raw)


    def select_files_bin(self):
        header = xasdata.XASdataGeneric.read_header(None, '{}/{}'.format(self.workingFolder,
                                                                         self.listFiles_bin.currentItem().text()))
        self.keys = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        self.keys.insert(0, '1')

        if 'timestamp' in self.keys:
            del self.keys[self.keys.index('timestamp')]

        if self.keys != self.last_keys:
            self.listWidget.clear()
            self.listWidget_2.clear()
            self.listWidget.insertItems(0, self.keys)
            self.listWidget_2.insertItems(0, self.keys)

            if self.last_num != '' and self.last_num <= len(self.keys) - 1:
                self.listWidget.setCurrentRow(self.last_num)
            if self.last_den != '' and self.last_den <= len(self.keys) - 1:
                self.listWidget_2.setCurrentRow(self.last_den)


    def plot_raw(self):
        self.push_save_bin.setEnabled(False)
        selected_items = (self.listFiles_raw.selectedItems())
        self.figure_raw.ax.clear()
        self.toolbar_raw._views.clear()
        self.toolbar_raw._positions.clear()
        self.toolbar_raw._update_view()
        self.canvas_raw.draw_idle()

        if self.listWidget_num_raw.currentRow() == -1 or self.listWidget_den_raw.currentRow() == -1:
            self.show_info_message('Error!', 'Please, select numerator and denominator')
            return

        self.last_num_raw = self.listWidget_num_raw.currentRow()
        self.last_den_raw = self.listWidget_den_raw.currentRow()

        if 'En. (eV)' in self.keys_raw:
            energy_key = 'En. (eV)'
        elif 'energy' in self.keys_raw:
            energy_key = 'energy'

        self.handles_raw = []
        for i in selected_items:
            self.gen.loadInterpFile('{}/{}'.format(self.workingFolder, i.text()))

            df = pd.DataFrame({k: v[:, 1] for k, v in self.gen.interp_arrays.items()}).sort_values(energy_key)

            division = df[self.listWidget_num_raw.currentItem().text()] \
                       / df[self.listWidget_den_raw.currentItem().text()]
            if self.checkBox_log_raw.checkState() :
                division = np.log(division)
            if self.checkBox_inv_raw.checkState():
                division = -division

            self.figure_raw.ax.plot(df[energy_key], division)
            self.figure_raw.ax.set_xlabel('Energy (eV)')
            self.figure_raw.ax.set_ylabel('{} / {}'.format(self.listWidget_num_raw.currentItem().text(), self.listWidget_den_raw.currentItem().text()))
            last_trace = self.figure_raw.ax.get_lines()[len(self.figure_raw.ax.get_lines()) - 1]
            last_trace.type = 'raw'
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            self.handles_raw.append(patch)

        self.figure_raw.ax.legend(handles=self.handles_raw)
        self.figure_raw.tight_layout()
        self.canvas_raw.draw_idle()


    def plot_bin(self):
        selected_items = (self.listFiles_bin.selectedItems())
        self.figure.ax.clear()
        self.toolbar._views.clear()
        self.toolbar._positions.clear()
        self.toolbar._update_view()
        self.canvas.draw_idle()

        if self.listWidget.currentRow() == -1 or self.listWidget_2.currentRow() == -1:
            self.show_info_message('Error!', 'Please, select numerator and denominator')
            return

        self.last_num = self.listWidget.currentRow()
        self.last_den = self.listWidget_2.currentRow()

        if 'En. (eV)' in self.keys:
            energy_key = 'En. (eV)'
        elif 'energy' in self.keys:
            energy_key = 'energy'

        handles = []
        for i in selected_items:
            self.gen.loadInterpFile('{}/{}'.format(self.workingFolder, i.text()))

            df = pd.DataFrame({k: v[:, 1] for k, v in self.gen.interp_arrays.items()}).sort_values(energy_key)

            division = df[self.listWidget.currentItem().text()] \
                       / df[self.listWidget_2.currentItem().text()]
            if self.checkBox_log_bin.checkState() :
                division = np.log(division)
            if self.checkBox_inv_bin.checkState():
                division = -division

            self.figure.ax.plot(df[energy_key], division)
            self.figure.ax.set_xlabel('Energy (eV)')
            self.figure.ax.set_ylabel('{} / {}'.format(self.listWidget.currentItem().text(), self.listWidget_2.currentItem().text()))
            last_trace = self.figure.ax.get_lines()[len(self.figure.ax.get_lines()) - 1]
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            handles.append(patch)

        self.figure.ax.legend(handles=handles)
        self.figure.tight_layout()
        self.canvas.draw_idle()


    def bin_data(self):
        for index, trace in enumerate(self.figure_raw.ax.get_lines()):
            if trace.type == 'binned':
                trace.remove()
                del self.handles_raw[-1]

        selected_items = [f.text() for f in self.listFiles_raw.selectedItems()]
        
        for index, f in enumerate(selected_items):
            filepath = '{}/{}'.format(self.workingFolder, f)

            e0 = float(self.edit_E0.text())
            edge_start = float(self.edit_edge_start.text())
            edge_end = float(self.edit_edge_end.text())
            preedge_spacing = float(self.edit_preedge_spacing.text())
            xanes_spacing = float(self.edit_xanes_spacing.text())
            exafs_spacing = float(self.edit_exafs_spacing.text())
            filepath = '{}/{}'.format(self.workingFolder, f)
            params = (e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_spacing, filepath)

            process_thread_bin = process_bin_thread(*params, index = index) 
            process_thread_bin.finished_bin.connect(self.plot_binned_data)
            process_thread_bin.start()


    def plot_binned_data(self, binned):
        result = binned[self.listWidget_num_raw.currentItem().text()] / binned[self.listWidget_den_raw.currentItem().text()]
        ylabel = '{} / {}'.format(self.listWidget_num_raw.currentItem().text(), self.listWidget_den_raw.currentItem().text())

        if self.checkBox_log_raw.isChecked():
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
        ylabel = 'Binned {}'.format(ylabel)
        xlabel = binned['energy_string']

        if self.checkBox_inv_raw.isChecked():
            result = -result

        self.figure_raw.ax.plot(binned[xlabel][:len(result)], result)
        last_trace = self.figure_raw.ax.get_lines()[len(self.figure_raw.ax.get_lines()) - 1]
        last_trace.type = 'binned'
        filepath = binned['filepath'][binned['filepath'].rfind('/') + 1 :] + ' (binned)'
        patch = mpatches.Patch(color=last_trace.get_color(), label=filepath)
        self.handles_raw.append(patch)

        self.figure_raw.ax.legend(handles=self.handles_raw)
        self.figure_raw.tight_layout()
        self.canvas_raw.draw_idle()

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
    def __init__(self, e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_spacing, filepath, index = 1):
        QThread.__init__(self)
        self.gen_parser = xasdata.XASdataGeneric(db = None)

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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = MyWindowClass()
    main.show()

    sys.exit(app.exec_())
