
import sys, os
import numpy as np
from PyQt4 import QtGui, uic
from PyQt4.QtCore import QSettings
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import  FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import pkg_resources
from isstools.xasdata import xasdata
import re
from databroker import Broker
from databroker.core import register_builtin_handlers
from bluesky.callbacks.broker import verify_files_saved, post_run
import metadataclient.mds as mdc
from filestore.fs import FileStore
import matplotlib.patches as mpatches

ui_path = pkg_resources.resource_filename('isstools', 'ui/Xview.ui')
gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class MyWindowClass(QtGui.QMainWindow, gui_form):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        #pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.selectWorkingFolder)
        self.pushbuttonRefreshFolder.clicked.connect(self.getFileList)
        self.pushbuttonPlotSelectedFiles.clicked.connect(self.plotSelectedFiles)
        #comboboxes
        self.comboBoxFileType.addItems( ['Raw (*.txt)', 'Binned(*.dat)','All'])
        self.comboBoxFileType.currentIndexChanged.connect((self.getFileList))
        self.comboBoxSortFilesBy.addItems(['Name', 'Time'])
        self.comboBoxSortFilesBy.currentIndexChanged.connect((self.getFileList))
        #file lists
        self.listFiles.itemSelectionChanged.connect(self.selectFilesToShow)
        self.listFiles.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []

        # Define databroker so we can use the generic parser correctly
        self.db = Broker(mdc, FileStore({'host': 'xf08id-ca1.cs.nsls2.local', 'port': 27017, 'database': 'filestore'}))
        self.db.mds = mdc.MDS({'host': 'xf08id-ca1.cs.nsls2.local', 'port': 7770,
                          'timezone': 'US/Eastern'})
        self.mds = self.db.mds

        # Create generic parser
        self.gen = xasdata.XASdataGeneric(self.db)
        #
        self.last_num = ''
        self.last_den = ''

        # Persistent settings
        self.settings = QSettings('ISS Beamline', 'Xview')
        self.workingFolder = self.settings.value('WorkingFolder', defaultValue = '/GPFS/xf08id/User Data', type = str)


        if self.workingFolder != '/GPFS/xf08id/User Data':
            self.labelWorkingFolder.setText(self.workingFolder)
            self.labelWorkingFolder.setToolTip(self.workingFolder)
            self.getFileList()


    def addCanvas(self):
        self.figure = Figure()
       # self.figure.set_facecolor(color='0.89')
        self.figure.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMaximumHeight(25)
        self.layout_plotRaw.addWidget(self.toolbar)
        self.layout_plotRaw.addWidget(self.canvas)
        self.canvas.draw()

    def figure_content(self):
        self.fig1 = Figure()
        self.fig1.set_facecolor(color='0.89')
        ax1f1 = self.fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        return self.fig1

    def selectWorkingFolder(self):
        self.workingFolder = QtGui.QFileDialog.getExistingDirectory(self, "Open a folder", self.workingFolder, QtGui.QFileDialog.ShowDirsOnly)
        self.settings.setValue('WorkingFolder', self.workingFolder)
        if len(self.workingFolder)>50:
            self.labelWorkingFolder.setText(self.workingFolder [1:20] + '...' + self.WorkingFolder[-30:])
        else:
            self.labelWorkingFolder.setText(self.workingFolder)
        self.labelWorkingFolder.setToolTip(self.workingFolder)
        self.getFileList()


    def getFileList(self):
        if self.workingFolder:
            self.listFiles.clear()
            if self.comboBoxFileType.currentText() == 'Raw (*.txt)':
                files = [f for f in os.listdir(self.workingFolder) if f.endswith('.txt')]
            elif self.comboBoxFileType.currentText() == 'Binned(*.dat)':
                files = [f for f in os.listdir(self.workingFolder) if f.endswith('.dat')]
            else:
                files = [f for f in os.listdir(self.workingFolder) if (f.endswith('.dat') or f.endswith('.txt'))]

            if self.comboBoxSortFilesBy.currentText() == 'Name':
                files.sort()
            elif self.comboBoxSortFilesBy.currentText() == 'Name':
                files.sort(key=lambda x: os.path.getmtime(x))
            self.listFiles.addItems(files)

    def selectFilesToShow(self):
        #print(self.list_RawFiles.currentItem().text())
        header = xasdata.XASdataGeneric.read_header(None, '{}/{}'.format(self.workingFolder,
                                                                         self.listFiles.currentItem().text()))
        self.keys = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        #print(self.keys)
        if self.keys != self.last_keys:
            self.listWidget.clear()
            self.listWidget_2.clear()
            self.listWidget.insertItems(0, self.keys)
            self.listWidget_2.insertItems(0, self.keys)

            if self.last_num != '' and self.last_num <= len(self.keys) - 1:
                self.listWidget.setCurrentRow(self.last_num)
            if self.last_den != '' and self.last_den <= len(self.keys) - 1:
                self.listWidget_2.setCurrentRow(self.last_den)
        #print(self.list_RawFiles.selectedItems())

    def plotSelectedFiles(self):
        selected_items=(self.listFiles.selectedItems())
        self.figure.ax.cla()
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
            index_margin = 10

            division = self.gen.interp_arrays[self.listWidget.currentItem().text()][index_margin:-index_margin, 1] \
                       / self.gen.interp_arrays[self.listWidget_2.currentItem().text()][index_margin:-index_margin, 1]
            if self.checkBoxApplyLog.checkState() :
                division = np.log(division)
            if self.checkBoxInvert.checkState():
                division = -division

            self.figure.ax.plot(self.gen.interp_arrays[energy_key][index_margin:-index_margin, 1], division)
            last_trace = self.figure.ax.get_lines()[len(self.figure.ax.get_lines()) - 1]
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            handles.append(patch)

        self.figure.ax.legend(handles=handles)
        self.canvas.draw_idle()

    def show_info_message(self, title, message):
        QtGui.QMessageBox.question(self,
                                   title,
                                   message,
                                   QtGui.QMessageBox.Ok)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    main = MyWindowClass()
    figure = main.figure_content()
   # main.addCanvas(figure)
    main.show()

    sys.exit(app.exec_())
