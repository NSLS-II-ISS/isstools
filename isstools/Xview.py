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
        self.xasproject.datasets_changed.connect(self.update_xas_project_list)


        # pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.select_working_folder)
        self.pushbuttonRefreshFolder.clicked.connect(self.getFileList)
        self.pushbutton_plot_bin.clicked.connect(self.plotBinnedData)
        self.comboBox_sort_files_by.addItems(['Time','Name'])
        self.comboBox_sort_files_by.currentIndexChanged.connect((self.getFileList))
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
            self.label_working_folder.setText(self.workingFolder)
            self.label_working_folder.setToolTip(self.workingFolder)
            self.getFileList()

        self.label_E0.setText("E<sub>0</sub>")
        # Setting up Preprocess tab:
        self.pushbutton_add_to_xasproject.clicked.connect(self.addDsToXASProject)
        self.listView_xasproject.itemSelectionChanged.connect(self.show_ds_params)
        self.listView_xasproject.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.pushbutton_remove_xasproject.clicked.connect(self.remove_from_xas_project)
        self.pushbutton_plotE_xasproject.clicked.connect(self.plot_xas_project_in_E)
        self.pushbutton_plotK_xasproject.clicked.connect(self.plot_xas_project_in_K)

        self.lineEdit_e0.textEdited.connect(self.update_ds_params)
        self.lineEdit_preedge_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_preedge_hi.textEdited.connect(self.update_ds_params)
        self.lineEdit_postedge_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_postedge_hi.textEdited.connect(self.update_ds_params)

        self.pushButton_e0_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_preedge_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_preedge_hi_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_postedge_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_postedge_hi_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_push_norm_param_to_selected.clicked.connect(self.push_norm_param)
        self.pushButton_push_norm_param_to_all.clicked.connect(self.push_norm_param)

        self.action_exit.triggered.connect(self.close_app)
        self.action_save_project.triggered.connect(self.save_xas_project)
        self.action_open_project.triggered.connect(self.open_xas_project)
        self.action_save_datasets_as_text.triggered.connect(self.save_xas_datasets_as_text)

    def close_app(self):
        self.close()

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
        self.figureXASProject.ax.grid(alpha = 0.4)
        self.canvasXASProject = FigureCanvas(self.figureXASProject)

        self.toolbar_XASProject = NavigationToolbar(self.canvasXASProject, self)
        self.layout_plot_xasproject.addWidget(self.toolbar_XASProject)
        self.layout_plot_xasproject.addWidget(self.canvasXASProject)
        self.canvasXASProject.draw()
        #layout_plot_xasproject

    def select_working_folder(self):
        self.workingFolder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a folder", self.workingFolder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        self.settings.setValue('WorkingFolder', self.workingFolder)
        if len(self.workingFolder) > 50:
            self.label_working_folder.setText(self.workingFolder[1:20] + '...' + self.WorkingFolder[-30:])
        else:
            self.label_working_folder.setText(self.workingFolder)
        self.getFileList()

    def getFileList(self):
        if self.workingFolder:
            self.listFiles_bin.clear()

            files_bin = [f for f in os.listdir(self.workingFolder) if f.endswith('.dat')]

            if self.comboBox_sort_files_by.currentText() == 'Name':
                files_bin.sort()
            elif self.comboBox_sort_files_by.currentText() == 'Time':
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
            spectrum = df[self.listBinnedDataNumerator.currentItem().text()] \
                       / df[self.listBinnedDataDenominator.currentItem().text()]
            if self.checkBox_log_bin.checkState():
                spectrum = np.log(spectrum)
            if self.checkBox_inv_bin.checkState():
                spectrum = -spectrum

            self.figureBinned.ax.plot(df[energy_key], spectrum)
            self.figureBinned.ax.set_xlabel('Energy (eV)')
            self.figureBinned.ax.set_ylabel('{} / {}'.format(self.listBinnedDataNumerator.currentItem().text(),
                                                             self.listBinnedDataDenominator.currentItem().text()))
            last_trace = self.figureBinned.ax.get_lines()[len(self.figureBinned.ax.get_lines()) - 1]
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            handles.append(patch)

        self.figureBinned.ax.legend(handles=handles)
        self.figureBinned.tight_layout()
        self.canvas.draw_idle()

    def push_norm_param(self):
        norm_param_list = [
            'e0',
            'pre1',
            'pre2',
            'norm1',
            'norm2',
        ]
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            sender = QObject()
            sender_object = sender.sender().objectName()
            index = selection[0].row()
            ds_master = self.xasproject[index]
            if sender_object == 'pushButton_push_norm_param_to_selected':
                for indx, obj in enumerate(selection):
                    ds = self.xasproject[ selection[indx].row()]
                    for param in norm_param_list:
                        setattr(ds, param, getattr(ds_master, param))
            if sender_object == 'pushButton_push_norm_param_to_all':
                for indx, obj in enumerate(self.xasproject):
                    for param in norm_param_list:
                        setattr(self.xasproject[indx], param, getattr(ds_master, param))



    # here we begin to work on the second pre-processing tab
    def update_ds_params(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            index=selection[0].row()
            ds = self.xasproject[index]
            sender_dict = {
                'lineEdit_preedge_lo': 'pre1',
                'lineEdit_preedge_hi': 'pre2',
                'lineEdit_postedge_lo': 'norm1',
                'lineEdit_postedge_hi': 'norm2',
                'lineEdit_e0': 'e0'
            }
            try:
                self.statusBar().showMessage(sender_object)
                setattr(ds, sender_dict[sender_object], float(getattr(self, sender_object).text()))
            except:
                self.statusBar().showMessage('Use numbers only')

    def set_ds_params_from_plot(self):
        sender = QObject()
        self.sender_object = sender.sender().objectName()
        self.statusBar().showMessage('Click on graph or press Esc')
        self.cid = self.canvasXASProject.mpl_connect('button_press_event',  self.mouse_press_event)

    def _disconnect_cid(self):
        if hasattr(self, 'cid'):
            self.canvasXASProject.mpl_disconnect(self.cid)
            delattr(self, 'cid')

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self._disconnect_cid()

    def mouse_press_event(self, event):
        sender_dict = {
            'pushButton_e0_set': 'lineEdit_e0',
            'pushButton_preedge_lo_set': 'lineEdit_preedge_lo',
            'pushButton_preedge_hi_set': 'lineEdit_preedge_hi',
            'pushButton_postedge_lo_set': 'lineEdit_postedge_lo',
            'pushButton_postedge_hi_set': 'lineEdit_postedge_hi',
        }
        lineEdit=getattr(self, sender_dict[self.sender_object])

        if  self.sender_object == 'pushButton_e0_set':
            new_value = event.xdata
        else:
            new_value = event.xdata-float(self.lineEdit_e0.text())

        lineEdit.setText('{:.1f}'.format(new_value))
        self._disconnect_cid()


    def show_ds_params(self):
        if self.listView_xasproject.selectedIndexes():
            index=self.listView_xasproject.selectedIndexes()[0]
            ds = self.xasproject[index.row()]
            self.lineEdit_e0.setText('{:.1f}'.format(ds.e0))
            self.lineEdit_preedge_lo.setText('{:.1f}'.format(ds.pre1))
            self.lineEdit_preedge_hi.setText('{:.1f}'.format(ds.pre2))
            self.lineEdit_postedge_lo.setText('{:.1f}'.format(ds.norm1))
            self.lineEdit_postedge_hi.setText('{:.1f}'.format(ds.norm2))
            # Make the first selected line bold, and reset bold font for other selections
            font = QtGui.QFont()
            font.setBold(False)
            for i in range(self.listView_xasproject.count()):
                self.listView_xasproject.item(i).setFont(font)
            font.setBold(True)
            self.listView_xasproject.item(index.row()).setFont(font)

    def addDsToXASProject(self):
        if self.listBinnedDataNumerator.currentRow() != -1 and self.listBinnedDataDenominator.currentRow() != -1:
            for item in self.listFiles_bin.selectedItems():
                filepath = str(Path(self.workingFolder) / Path(item.text()))
                name = Path(filepath).resolve().stem
                header = self.gen_parser.read_header(filepath)
                uid = header[header.find('real_uid:')+10:header.find('\n', header.find('real_uid:'))]
                md = self.db[uid]['start']

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
                mu=np.array(mu)
                ds = xasproject.XASDataSet(name=name,md=md,energy=df['energy'],mu=mu, filename=filepath,datatype='experiment')
                ds.header = header
                self.xasproject.append(ds)
                self.statusBar().showMessage('Scans added to the project successfully')
        else:
            self.statusBar().showMessage('Select numerator and denominator columns')


    def update_xas_project_list(self, datasets):
        self.listView_xasproject.clear()
        print('a')
        for ds in datasets:
            fn = ds.filename
            fn = fn[fn.rfind('/') + 1:]
            self.listView_xasproject.addItem(fn)

    def remove_from_xas_project(self):
        for index in self.listView_xasproject.selectedIndexes()[::-1]: #[::-1] to remove using indexes from last to first
            self.xasproject.removeDatasetIndex(index.row())
            print('delete')

    def plot_xas_project_in_E(self):
        self.figureXASProject.ax.clear()
        self.toolbar_XASProject._views.clear()
        self.toolbar_XASProject._positions.clear()
        self.toolbar_XASProject._update_view()
        self.canvasXASProject.draw_idle()

        for index in self.listView_xasproject.selectedIndexes():
            ds = self.xasproject[index.row()]
            ds.subtract_background_force()
        #for ds in self.xasproject:
            energy = ds.energy
            if self.radioButton_mu_xasproject.isChecked():
                data = ds.mu
            elif self.radioButton_norm_xasproject.isChecked():
                if self.checkBox_norm_flat_xasproject.checkState():
                    data = ds.flat
                else:
                    data = ds.norm
            if self.checkBox_deriv.isChecked():
                data = ds.mu_deriv
                energy = ds.energy_deriv
            self.figureXASProject.ax.plot(energy, data, label = ds.name)

            if self.radioButton_mu_xasproject.isChecked() and not self.checkBox_deriv.isChecked():
                if self.checkBox_preedge_show.checkState():
                    line = self.figureXASProject.ax.plot(ds.energy, ds.pre_edge,label='Preedge', linewidth=0.75)
                if self.checkBox_postedge_show.checkState():
                    self.figureXASProject.ax.plot(ds.energy, ds.post_edge, label='Postedge', linewidth=0.75)
                if self.checkBox_background_show.checkState():
                    self.figureXASProject.ax.plot(ds.energy, ds.bkg, label='Background', linewidth=0.75)

        self.figureXASProject.ax.legend(fontsize = 'small')
        self.figureXASProject.ax.grid(alpha=0.4)
        self.figureXASProject.ax.set_ylabel(r'$\chi  \mu$' + '(E)', size='13')
        self.figureXASProject.ax.set_xlabel('Energy /eV', size='13')
        self.canvasXASProject.draw_idle()


    def plot_xas_project_in_K(self):
        self.figureXASProject.ax.clear()
        self.toolbar_XASProject._views.clear()
        self.toolbar_XASProject._positions.clear()
        self.toolbar_XASProject._update_view()
        self.canvasXASProject.draw_idle()

        for index in self.listView_xasproject.selectedIndexes():
            ds = self.xasproject[index.row()]
            ds.extract_chi()
            if self.radioButton_k_weight_1.isChecked():
                data=ds.k*ds.chi
            elif self.radioButton_k_weight_2.isChecked():
                data = ds.k *ds.k * ds.chi
            elif self.radioButton_k_weight_3.isChecked():
                data = ds.k * ds.k * ds. k* ds.chi
            self.figureXASProject.ax.plot(ds.k, data, label = ds.name)


        self.figureXASProject.ax.legend(fontsize = 'small')
        self.figureXASProject.ax.grid(alpha=0.4)
        self.figureXASProject.ax.set_ylabel(r'$\chi  \mu$' + '(k)', size='13')
        self.figureXASProject.ax.set_xlabel(('k (' + r'$\AA$' + '$^1$' +')'), size='13')
        self.canvasXASProject.draw_idle()
        self.canvasXASProject.draw_idle()

    def save_xas_project(self):
        options = QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project as', self.workingFolder,
                                                  'XAS project files (*.xas)', options=options)
        if filename:
            if Path(filename).suffix != '.xas':
                filename = filename + '.xas'
            print(filename)
            self.xasproject.save(filename=filename)
            
    def open_xas_project(self):
        options = QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load XAS project', self.workingFolder,
                                                  'XAS project files (*.xas)', options=options)
        if filename:
            self.xasproject_loaded_from_file = xasproject.XASProject()
            self.xasproject_loaded_from_file.load(filename = filename)

            if ret == 0:
                self.xasproject = self.xasproject_loaded_from_file
                self.update_xas_project_list(self.xasproject._datasets)
            if ret == 1:
                for i in self.xasproject_loaded_from_file._datasets:
                    self.xasproject.append(i)

    def save_xas_datasets_as_text(self):
        #options = QtWidgets.QFileDialog.DontUseNativeDialog
        #filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project as', self.workingFolder,
        #                                          'XAS project files (*.xas)', options=options)
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            messageBox = QtWidgets.QMessageBox()
            messageBox.setText('Save datasets as..')
            messageBox.addButton(QtWidgets.QPushButton('mu(E)'), QtWidgets.QMessageBox.YesRole)
            messageBox.addButton(QtWidgets.QPushButton('normalized mu(E)'), QtWidgets.QMessageBox.NoRole)
            messageBox.addButton(QtWidgets.QPushButton('flattened mu(E)'), QtWidgets.QMessageBox.NoRole)
            ret = messageBox.exec_()
            options = QtWidgets.QFileDialog.DontUseNativeDialog
            pathname = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose folder...', self.workingFolder,
                                                                    options=options)
            separator = '#______________________________________________________\n'
            if pathname is not '':
                for indx, obj in enumerate(selection):
                    ds = self.xasproject._datasets[ selection[indx].row()]
                    filename = str(Path(ds.filename).stem)
                    if ret == 0:
                        xx = ds.energy
                        yy = ds.mu
                        keys = '# energy(eV), mu(E)\n'
                    elif ret == 1:
                        xx = ds.energy
                        yy = ds.norm
                        keys = '# energy(eV), normalized mu(E)\n'
                    elif ret == 2:
                        xx = ds.energy
                        yy = ds.flat
                        keys = '# energy(eV), flattened normalized mu(E)\n'
                    filename_new = '{}/{}.{}'.format(pathname,filename,'mu')
                    print(filename_new)
                    fid = open(filename_new, 'w')
                    print(fid)
                    header_wo_cols_names = ds.header[0:ds.header.rfind('#')]
                    fid.write(header_wo_cols_names)
                    fid.write(separator)
                    fid.write(keys)
                    fid.close()








            # if Path(filename).suffix != '.xas':
            #     filename = filename + '.xas'a=
            # print(filename)
            # self.xasproject.save(filename=filename)





if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())
