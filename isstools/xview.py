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



from isstools.xasproject import xasproject
from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file


ui_path = pkg_resources.resource_filename('isstools', 'ui/Xview.ui')
#gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class XviewGui(*uic.loadUiType(ui_path)):

#class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self, db=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.db = db
        self.xasproject = xasproject.XASProject()
        self.xasproject.datasets_changed.connect(self.update_xas_project_list)

        # pushbuttons
        self.pushbuttonSelectFolder.clicked.connect(self.select_working_folder)
        self.pushbuttonRefreshFolder.clicked.connect(self.get_file_list)
        self.pushbutton_plot_bin.clicked.connect(self.plotBinnedData)
        self.comboBox_sort_files_by.addItems(['Time','Name'])
        self.comboBox_sort_files_by.currentIndexChanged.connect((self.get_file_list))
        # file lists
        self.listFiles_bin.itemSelectionChanged.connect(self.select_files_to_plot)
        self.listFiles_bin.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []
        self.current_plot_in = ''
        self.binned_data = []
        self.last_num = ''
        self.last_den = ''


        # Persistent settings
        self.settings = QSettings('ISS Beamline', 'Xview')
        self.workingFolder = self.settings.value('WorkingFolder', defaultValue='/GPFS/xf08id/User Data', type=str)

        if self.workingFolder != '/GPFS/xf08id/User Data':
            self.label_working_folder.setText(self.workingFolder)
            self.label_working_folder.setToolTip(self.workingFolder)
            self.get_file_list()

        self.label_E0.setText("E<sub>0</sub>")
        # Setting up Preprocess tab:
        self.pushbutton_add_to_xasproject.clicked.connect(self.add_files_to_xas_project)
        self.listView_xasproject.itemSelectionChanged.connect(self.show_ds_params)
        self.listView_xasproject.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.pushbutton_plotE_xasproject.clicked.connect(self.plot_xas_project_in_E)
        self.pushbutton_plotK_xasproject.clicked.connect(self.plot_xas_project_in_K)
        self.pushbutton_plotR_xasproject.clicked.connect(self.plot_xas_project_in_R)
        self.lineEdit_e0.textEdited.connect(self.update_ds_params)
        self.lineEdit_preedge_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_preedge_hi.textEdited.connect(self.update_ds_params)
        self.lineEdit_postedge_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_postedge_hi.textEdited.connect(self.update_ds_params)
        self.lineEdit_spline_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_spline_hi.textEdited.connect(self.update_ds_params)
        self.lineEdit_clamp_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_clamp_hi.textEdited.connect(self.update_ds_params)
        self.lineEdit_k_ft_lo.textEdited.connect(self.update_ds_params)
        self.lineEdit_k_ft_hi.textEdited.connect(self.update_ds_params)

        self.pushButton_e0_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_preedge_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_preedge_hi_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_postedge_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_postedge_hi_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_spline_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_spline_hi_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_k_ft_lo_set.clicked.connect(self.set_ds_params_from_plot)
        self.pushButton_k_ft_hi_set.clicked.connect(self.set_ds_params_from_plot)

        self.pushButton_truncate_at_set.clicked.connect(self.set_ds_params_from_plot)

        # Push to selected/all  buttons defs
        self.pushButton_push_norm_param_to_selected.clicked.connect(self.push_param)
        self.pushButton_push_norm_param_to_all.clicked.connect(self.push_param)
        self.pushButton_push_bkg_param_to_selected.clicked.connect(self.push_param)
        self.pushButton_push_bkg_param_to_all.clicked.connect(self.push_param)

        self.pushButton_truncate_below.clicked.connect(self.truncate)
        self.pushButton_truncate_above.clicked.connect(self.truncate)

        #Menu defs
        self.action_exit.triggered.connect(self.close_app)
        self.action_save_project.triggered.connect(self.save_xas_project)
        self.action_open_project.triggered.connect(self.open_xas_project)
        self.action_save_datasets_as_text.triggered.connect(self.save_xas_datasets_as_text)
        self.action_combine_and_save_as_text.triggered.connect(self.combine_and_save_xas_datasets_as_text)
        self.action_merge.triggered.connect(self.merge_datasets)
        self.action_rename.triggered.connect(self.rename_dataset)
        self.action_remove.triggered.connect(self.remove_from_xas_project)

        self.lineEdit_to_ds_parameter_dict = {
            'lineEdit_preedge_lo':  'pre1',
            'lineEdit_preedge_hi':  'pre2',
            'lineEdit_postedge_lo': 'norm1',
            'lineEdit_postedge_hi': 'norm2',
            'lineEdit_e0':          'e0',
            'lineEdit_spline_lo':   'kmin',
            'lineEdit_spline_hi':   'kmax',
            'lineEdit_clamp_lo':    'clamp_lo',
            'lineEdit_clamp_hi':    'clamp_hi',
            'lineEdit_truncate_at': 'truncate',
            'lineEdit_k_ft_lo':     'kmin_ft',
            'lineEdit_k_ft_hi':     'kmax_ft'
        }

        self.pushButton_set_to_lineEdit_dict = {
            'pushButton_e0_set':           'lineEdit_e0',
            'pushButton_preedge_lo_set':   'lineEdit_preedge_lo',
            'pushButton_preedge_hi_set':   'lineEdit_preedge_hi',
            'pushButton_postedge_lo_set':  'lineEdit_postedge_lo',
            'pushButton_postedge_hi_set':  'lineEdit_postedge_hi',
            'pushButton_spline_lo_set':    'lineEdit_spline_lo',
            'pushButton_spline_hi_set':    'lineEdit_spline_hi',
            'pushButton_k_ft_lo_set':      'lineEdit_k_ft_lo',
            'pushButton_k_ft_hi_set':      'lineEdit_k_ft_hi',
            'pushButton_truncate_at_set':  'lineEdit_truncate_at'
        }
        self.windows_list = [
            'hanning',
            'kaiser',
            'gaussian',
            'sine'
        ]


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
        self.layout_plot_xasproject.addWidget(self.canvasXASProject)
        self.layout_plot_xasproject.addWidget(self.toolbar_XASProject)

        self.canvasXASProject.draw()
        #layout_plot_xasproject

    def select_working_folder(self):
        self.workingFolder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a folder", self.workingFolder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        if  self.workingFolder:
            self.settings.setValue('WorkingFolder', self.workingFolder)
            if len(self.workingFolder) > 50:
                self.label_working_folder.setText(self.workingFolder[1:20] + '...' + self.WorkingFolder[-30:])
            else:
                self.label_working_folder.setText(self.workingFolder)
            self.get_file_list()

    def get_file_list(self):
        if self.workingFolder:
            self.listFiles_bin.clear()

            files_bin = [f for f in os.listdir(self.workingFolder) if f.endswith('.dat')]

            if self.comboBox_sort_files_by.currentText() == 'Name':
                files_bin.sort()
            elif self.comboBox_sort_files_by.currentText() == 'Time':
                files_bin.sort(key=lambda x: os.path.getmtime('{}/{}'.format(self.workingFolder, x)))

                files_bin.reverse()
            self.listFiles_bin.addItems(files_bin)

    def select_files_to_plot(self):
        df, header = load_binned_df_from_file(f'{self.workingFolder}/{self.listFiles_bin.currentItem().text()}')
        keys = df.keys()
        refined_keys = []
        for key in keys:
            if not (('timestamp' in key) or ('energy' in key)):
                refined_keys.append(key)
        self.keys = refined_keys
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
        self.toolbar.update()
        self.figureBinned.ax.grid(alpha=0.4)
        # self.toolbar._views.clear()
        # self.toolbar._positions.clear()
        # self.toolbar._update_view()
        self.canvas.draw_idle()
        if self.listBinnedDataNumerator.currentRow() == -1 or self.listBinnedDataDenominator.currentRow() == -1:
            self.statusBar().showMessage('Please select numerator and denominator')
            return

        self.last_num = self.listBinnedDataNumerator.currentRow()
        self.last_den = self.listBinnedDataDenominator.currentRow()

        energy_key = 'energy'

        handles = []

        for i in selected_items:
            path = f'{self.workingFolder}/{i.text()}'
            print(path)
            df, header = load_binned_df_from_file(path)
            numer = np.array(df[self.listBinnedDataNumerator.currentItem().text()])
            denom = np.array(df[self.listBinnedDataDenominator.currentItem().text()])
            if self.checkBox_ratio.checkState():
                y_label = (f'{self.listBinnedDataNumerator.currentItem().text()} / '
                           f'{self.listBinnedDataDenominator.currentItem().text()}')
                spectrum = numer/denom
            else:
                y_label = (f'{self.listBinnedDataNumerator.currentItem().text()}')
                spectrum = numer
            if self.checkBox_log_bin.checkState():
                spectrum = np.log(spectrum)
                y_label = f'ln ({y_label})'
            if self.checkBox_inv_bin.checkState():
                spectrum = -spectrum
                y_label = f'- {y_label}'

            self.figureBinned.ax.plot(df[energy_key], spectrum)
            self.figureBinned.ax.set_xlabel('Energy (eV)')
            self.figureBinned.ax.set_ylabel(y_label)
            last_trace = self.figureBinned.ax.get_lines()[len(self.figureBinned.ax.get_lines()) - 1]
            patch = mpatches.Patch(color=last_trace.get_color(), label=i.text())
            handles.append(patch)

        self.figureBinned.ax.legend(handles=handles)
        self.figureBinned.tight_layout()
        self.canvas.draw_idle()

    def push_param(self):
        self.norm_param_list = [
            'e0',
            'pre1',
            'pre2',
            'norm1',
            'norm2',
        ]

        self.bkg_param_list = [
            'kmin',
            'kmax',
            'clamp_lo',
            'clamp_hi'
        ]
        self.ft_param_list =[

        ]
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            sender = QObject()
            sender_object = sender.sender().objectName()
            index = selection[0].row()
            ds_master = self.xasproject[index]
            if sender_object == 'pushButton_push_norm_param_to_selected':
                for indx, obj in enumerate(selection):
                    ds = self.xasproject[selection[indx].row()]
                    for param in self.norm_param_list:
                        setattr(ds, param, getattr(ds_master, param))
            if sender_object == 'pushButton_push_norm_param_to_all':
                for indx, obj in enumerate(self.xasproject):
                    for param in self.norm_param_list:
                        setattr(self.xasproject[indx], param, getattr(ds_master, param))
            if sender_object == 'pushButton_push_bkg_param_to_selected':
                for indx, obj in enumerate(selection):
                    ds = self.xasproject[selection[indx].row()]
                    for param in self.bkg_param_list:
                        setattr(ds, param, getattr(ds_master, param))
            if sender_object == 'pushButton_push_bkg_param_to_all':
                for indx, obj in enumerate(self.xasproject):
                    for param in self.bkg_param_list:
                        setattr(self.xasproject[indx], param, getattr(ds_master, param))





    # here we begin to work on the second pre-processing tab
    def update_ds_params(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        print(sender_object)
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            index=selection[0].row()
            ds = self.xasproject[index]
            try:
                self.statusBar().showMessage(sender_object)
                print(getattr(self, sender_object).text())
                setattr(ds, self.lineEdit_to_ds_parameter_dict[sender_object], float(getattr(self, sender_object).text()))
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

        e_vs_k_discriminate_list = ['pushButton_spline_lo_set',
                                    'pushButton_spline_hi_set',
                                    'pushButton_k_ft_lo_set',
                                    'pushButton_k_ft_hi_set'
                                    ]

        lineEdit=getattr(self, self.pushButton_set_to_lineEdit_dict[self.sender_object])
        e0=float(self.lineEdit_e0.text())
        if self.sender_object == 'pushButton_e0_set':
            new_value = event.xdata

        elif self.sender_object == 'pushButton_truncate_at_set':
            if self.current_plot_in == 'e':
                new_value = event.xdata
            elif self.current_plot_in == 'k':
                new_value = k2e(event.xdata, e0)

        elif self.sender_object in e_vs_k_discriminate_list:
            if self.current_plot_in == 'k':
                new_value = event.xdata
            elif self.current_plot_in == 'e':
                new_value = e2k(event.xdata, e0)
        else:
            new_value = event.xdata-e0

        lineEdit.setText('{:.1f}'.format(new_value))
        sender_object = lineEdit

        print (sender_object)
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            index=selection[0].row()
            ds = self.xasproject[index]
            try:
                float(sender_object.text())
                setattr(ds, self.lineEdit_to_ds_parameter_dict[sender_object.objectName()], float(sender_object.text()))
            except:
                print('what''s going wrong')

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
            self.lineEdit_spline_lo.setText('{:.1f}'.format(ds.kmin))
            self.lineEdit_spline_hi.setText('{:.1f}'.format(ds.kmax))
            self.lineEdit_clamp_lo.setText('{:.1f}'.format(ds.clamp_lo))
            self.lineEdit_clamp_hi.setText('{:.1f}'.format(ds.clamp_hi))
            self.lineEdit_k_ft_lo.setText('{:.1f}'.format(ds.kmin_ft))
            self.lineEdit_k_ft_hi.setText('{:.1f}'.format(ds.kmax_ft))

            # Make the first selected line bold, and reset bold font for other selections
            font = QtGui.QFont()
            font.setBold(False)

            for i in range(self.listView_xasproject.count()):
                self.listView_xasproject.item(i).setFont(font)
            font.setBold(True)
            self.listView_xasproject.item(index.row()).setFont(font)

    def add_files_to_xas_project(self):
        if self.listBinnedDataNumerator.currentRow() != -1 and self.listBinnedDataDenominator.currentRow() != -1:
            for item in self.listFiles_bin.selectedItems():
                filepath = str(Path(self.workingFolder) / Path(item.text()))

                name = Path(filepath).resolve().stem
                df, header = load_binned_df_from_file(filepath)
                uid = header[header.find('UID:')+5:header.find('\n', header.find('UID:'))]


                try:
                    md = self.db[uid]['start']
                except:
                    print('Metadata not found')
                    md={}

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
        for ds in datasets:
            self.listView_xasproject.addItem(ds.name)

    def remove_from_xas_project(self):
        for index in self.listView_xasproject.selectedIndexes()[::-1]: #[::-1] to remove using indexes from last to first
            self.xasproject.removeDatasetIndex(index.row())
            self.statusBar().showMessage('Datasets deleted')

    def plot_xas_project_in_E(self):
        if self.listView_xasproject.selectedIndexes():
            self.reset_figure(self.figureXASProject.ax, self.toolbar_XASProject, self.canvasXASProject)

            for index in self.listView_xasproject.selectedIndexes():
                ds = self.xasproject[index.row()]
                ds.normalize_force()
                ds.extract_chi_force()
                ds.extract_ft()
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
                        self.figureXASProject.ax.plot(ds.energy, ds.pre_edge,label='Preedge', linewidth=0.75)
                    if self.checkBox_postedge_show.checkState():
                        self.figureXASProject.ax.plot(ds.energy, ds.post_edge, label='Postedge', linewidth=0.75)
                    if self.checkBox_background_show.checkState():
                        self.figureXASProject.ax.plot(ds.energy, ds.bkg, label='Background', linewidth=0.75)


            self.set_figure(self.figureXASProject.ax, self.canvasXASProject,label_x ='Energy /eV',
                       label_y =r'$\chi  \mu$' + '(E)'),

            if self.checkBox_force_range_E.checkState():
                self.figureXASProject.ax.set_xlim((float(self.lineEdit_e0.text())+float(self.lineEdit_range_E_lo.text())),
                                                  (float(self.lineEdit_e0.text()) + float(self.lineEdit_range_E_hi.text())))
            self.current_plot_in = 'e'


    def plot_xas_project_in_K(self):
        if self.listView_xasproject.selectedIndexes():
            self.reset_figure(self.figureXASProject.ax, self.toolbar_XASProject, self.canvasXASProject)
            window=self.set_ft_window()
            for index in self.listView_xasproject.selectedIndexes():
                ds = self.xasproject[index.row()]
                ds.extract_chi_force()
                ds.extract_ft_force(window = window)

                data = ds.chi * np.power(ds.k,self.spinBox_k_weight.value())

                self.figureXASProject.ax.plot(ds.k, data, label = ds.name)
                data_max = data.max()
                if self.checkBox_show_window.isChecked():
                    self.figureXASProject.ax.plot(ds.k, ds.kwin*data_max/2, label='Windows')


            self.set_figure(self.figureXASProject.ax, self.canvasXASProject,label_x ='k (' + r'$\AA$' + '$^1$' +')',
                       label_y =r'$\chi  \mu$' + '(k)')


            if self.checkBox_force_range_k.checkState():
                self.figureXASProject.ax.set_xlim(float(self.lineEdit_range_k_lo.text()),
                                                  float(self.lineEdit_range_k_hi.text()))
            self.current_plot_in = 'k'

    def plot_xas_project_in_R(self):
        if self.listView_xasproject.selectedIndexes():
            self.reset_figure(self.figureXASProject.ax,self.toolbar_XASProject, self.canvasXASProject)
            window = self.set_ft_window()
            for index in self.listView_xasproject.selectedIndexes():
                ds = self.xasproject[index.row()]
                ds.extract_ft_force(window=window)
                if self.checkBox_show_chir_mag.checkState():
                    self.figureXASProject.ax.plot(ds.r, ds.chir_mag, label = ds.name)
                if self.checkBox_show_chir_im.checkState():
                    self.figureXASProject.ax.plot(ds.r, ds.chir_im, label=(ds.name + ' Im'))
                if self.checkBox_show_chir_re.checkState():
                    self.figureXASProject.ax.plot(ds.r, ds.chir_re, label=(ds.name + ' Re'))
                #if self.checkBox_show_chir_pha.checked:
                #    self.figureXASProject.ax.plot(ds.r, ds.chir_pha, label=(ds.name + ' Ph'))

            self.set_figure(self.figureXASProject.ax,self.canvasXASProject, label_y=r'$\chi  \mu$' + '(k)',
                       label_x='R (' + r'$\AA$'  +')')
            if self.checkBox_force_range_R.checkState():
                self.figureXASProject.ax.set_xlim(float(self.lineEdit_range_R_lo.text()),
                                                  float(self.lineEdit_range_R_hi.text()))
            self.current_plot_in = 'R'


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
            ret = self.message_box_save_datasets_as()
            options = QtWidgets.QFileDialog.DontUseNativeDialog
            pathname = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose folder...', self.workingFolder,
                                                                    options=options)
            separator = '#______________________________________________________\n'
            if pathname is not '':
                for indx, obj in enumerate(selection):
                    ds = self.xasproject._datasets[selection[indx].row()]
                    filename = ds.name
                    if ret == 0:
                        xx = ds.energy
                        yy = np.array(ds.mu.mu)
                        keys = '# energy(eV), mu(E)\n'
                    elif ret == 1:
                        xx = ds.energy
                        yy = ds.norm
                        keys = '# energy(eV), normalized mu(E)\n'
                    elif ret == 2:
                        xx = ds.energy
                        yy = ds.flat
                        keys = '# energy(eV), flattened normalized mu(E)\n'
                    table = np.stack((xx, yy)).T

                    filename_new = '{}/{}.{}'.format(pathname,filename,'mu')
                    fid = open(filename_new, 'w')
                    header_wo_cols_names = ds.header[0:ds.header.rfind('#')]
                    fid.write(header_wo_cols_names)
                    fid.write(separator)
                    fid.write(keys)
                    fid.close()

                    fid = open(filename_new, 'a')
                    np.savetxt(fid,table)
                    fid.close()

    def merge_datasets(self):

        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:

            mu = self.xasproject._datasets[selection[0].row()].mu
            energy_master=self.xasproject._datasets[selection[0].row()].energy
            mu_array=np.zeros([len(selection),len(mu)])
            energy = self.xasproject._datasets[selection[0].row()].energy
            md=['# merged \n']
            for indx, obj in enumerate(selection):

                energy = self.xasproject._datasets[selection[indx].row()].energy
                mu = self.xasproject._datasets[selection[indx].row()].mu.mu
                mu = np.interp(energy_master, energy, mu)
                mu_array[indx, :]=mu
                md.append('# ' + self.xasproject._datasets[selection[indx].row()].filename + '\n')


            mu_merged = np.average(mu_array, axis=0)
            merged = xasproject.XASDataSet(name='merge', md=md, energy=energy, mu=mu_merged, filename='',
                                     datatype='processed')
            merged.header = "".join(merged.md)
            merged.filename
            self.xasproject.append(merged)
            self.xasproject.project_changed()



    def combine_and_save_xas_datasets_as_text(self):
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            ds_list = []
            md = []
            for indx, obj in enumerate(selection):
                ds_list.append(self.xasproject._datasets[selection[indx].row()])

            ds_list.sort(key=lambda x: x.name)
            mu = ds_list[0].mu
            mu_array = np.zeros([len(selection)+1, len(mu)])
            energy_master = ds_list[0].energy

            mu_array[0, :]=energy_master
            ret = self.message_box_save_datasets_as()
            for indx, obj in enumerate(selection):
                ds = ds_list[indx]
                energy=ds.energy
                if ret == 0:
                    yy = np.array(ds.mu.mu)
                    keys = '# energy(eV), mu(E)\n'
                elif ret == 1:
                    yy = ds.norm
                    keys = '# energy(eV), normalized mu(E)\n'
                elif ret == 2:
                    yy = ds.flat
                    keys = '# energy(eV), flattened normalized mu(E)\n'

                yy=np.interp(energy_master,energy,yy)
                mu_array[indx+1, :] = yy
                md.append(ds.name)

            self.mu_array = mu_array
            options = QtWidgets.QFileDialog.DontUseNativeDialog
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project', self.workingFolder,
                                                                'XAS dataset (*.dat)', options=options)
            if filename:
                if Path(filename).suffix != '.xas':
                    filename = filename + '.xas'
                print(filename)
                filelist = "{}".format("\n".join(md[0:]))
                separator = '\n #______________________________________________________\n'

                header = '{} {} {}'.format(filelist,separator,keys)
                fid = open(filename, 'w')
                np.savetxt(fid, np.transpose(mu_array), header = header)
                fid.close()

    def rename_dataset(self):
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            name = self.xasproject._datasets[selection[0].row()].name
            new_name, ok = QtWidgets.QInputDialog.getText(self, 'Rename dataset', 'Enter new name:',QtWidgets.QLineEdit.Normal, name)
            if ok:
                self.xasproject._datasets[selection[0].row()].name=new_name
                self.xasproject.project_changed()

    def truncate(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        print(sender_object)
        selection = self.listView_xasproject.selectedIndexes()
        if selection != []:
            for indx, obj in enumerate(selection):
                print(indx)
                ds = self.xasproject._datasets[selection[indx].row()]
                print(ds.name)
                energy=ds.energy
                mu  = ds.mu
                indx_energy_to_truncate_at = (np.abs(energy - float(self.lineEdit_truncate_at.text()))).argmin()

                if sender_object == 'pushButton_truncate_below':
                    ds.energy = energy[indx_energy_to_truncate_at:]
                    ds.mu = mu[indx_energy_to_truncate_at:]

                elif sender_object == 'pushButton_truncate_above':
                    ds.energy = energy[0:indx_energy_to_truncate_at]

                    ds.mu = mu[0:indx_energy_to_truncate_at:]
                ds.update_larch()
                self.xasproject._datasets[selection[indx].row()]=ds

    '''
     
     Service routines
     
     '''

    def set_figure(self,axis,canvas, label_x='', label_y=''):
        axis.legend(fontsize='small')
        axis.grid(alpha=0.4)
        axis.set_ylabel(label_y, size='13')
        axis.set_xlabel(label_x, size='13')
        canvas.draw_idle()

    def reset_figure(self,axis,toolbar,canvas):
        axis.clear()
        toolbar.update()
        # toolbar._views.clear()
        # toolbar._positions.clear()
        # toolbar._update_view()
        canvas.draw_idle()


    def message_box_save_datasets_as(self):
        messageBox = QtWidgets.QMessageBox()
        messageBox.setText('Save datasets as..')
        messageBox.addButton(QtWidgets.QPushButton('mu(E)'), QtWidgets.QMessageBox.YesRole)
        messageBox.addButton(QtWidgets.QPushButton('normalized mu(E)'), QtWidgets.QMessageBox.NoRole)
        messageBox.addButton(QtWidgets.QPushButton('flattened mu(E)'), QtWidgets.QMessageBox.NoRole)
        ret = messageBox.exec_()
        return ret

    def message_box_warning(self,line1='Warning', line2=''):

        messageBox = QtWidgets.QMessageBox()
        messageBox.setText(line1)
        if line2:
            messageBox.setInformativeText(line2)
        messageBox.setWindowTitle("Warning")
        messageBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        messageBox.exec_()

    def set_ft_window(self):
        window = dict()
        window['window_type'] = self.windows_list[self.comboBox_window.currentIndex()]
        window['r_weight'] = self.spinBox_r_weight.value()
        try:
            window['tapering'] = float(self.lineEdit_window_tapering.text())
        except:
            window['tapering'] = 1

        return window

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())


