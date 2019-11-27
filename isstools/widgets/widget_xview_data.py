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
from PyQt5.QtWidgets import QMenu
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from sys import platform
from pathlib import Path
from isstools.dialogs.BasicDialogs import message_box

from matplotlib.figure import Figure

from isstools.xasproject import xasproject
from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file


if platform == 'darwin':
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview-mac.ui')
else:
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview_data.ui')


class UIXviewData(*uic.loadUiType(ui_path)):


    def __init__(self, db=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.db = db
        self.push_select_folder.clicked.connect(self.select_working_folder)
        self.push_refresh_folder.clicked.connect(self.get_file_list)
        self.push_plot_bin.clicked.connect(self.plot_xas_data)
        self.comboBox_sort_files_by.addItems(['Time','Name'])
        self.comboBox_sort_files_by.currentIndexChanged.connect((self.get_file_list))
        self.list_data.itemSelectionChanged.connect(self.select_files_to_plot)
        self.push_add_to_project.clicked.connect(self.add_files_to_xas_project)


        self.list_data.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_data.customContextMenuRequested.connect(self.xas_data_context_menu)



        self.list_data.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.addCanvas()
        self.keys = []
        self.last_keys = []
        self.current_plot_in = ''
        self.binned_data = []
        self.last_num = ''
        self.last_den = ''


        # Persistent settings
        self.settings = QSettings('ISS Beamline', 'Xview')
        self.working_folder = self.settings.value('working_folder', defaultValue='/GPFS/xf08id/User Data', type=str)

        if self.working_folder != '/GPFS/xf08id/User Data':
            self.label_working_folder.setText(self.working_folder)
            self.label_working_folder.setToolTip(self.working_folder)
            self.get_file_list()

        # Setting up Preprocess tab:

        # Push to selected/all  buttons defs



        #Menu defs
        # self.action_exit.triggered.connect(self.close_app)
        # self.action_save_project.triggered.connect(self.save_xas_project)
        # self.action_open_project.triggered.connect(self.open_xas_project)
        # self.action_save_datasets_as_text.triggered.connect(self.save_xas_datasets_as_text)
        # self.action_combine_and_save_as_text.triggered.connect(self.combine_and_save_xas_datasets_as_text)
        # self.action_merge.triggered.connect(self.merge_datasets)
        # self.action_rename.triggered.connect(self.rename_dataset)
        # self.action_remove.triggered.connect(self.remove_from_xas_project)


    def xas_data_context_menu(self,QPos):
        menu = QMenu()
        plot_action = menu.addAction("&Plot")
        add_to_project_action = menu.addAction("&Add to project")
        parentPosition = self.list_data.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == plot_action:
            self.plot_xas_data()
        elif action == add_to_project_action:
            self.add_files_to_xas_project()



    def close_app(self):
        self.close()

    def addCanvas(self):
        self.figureBinned = Figure()
        self.figureBinned.set_facecolor(color='#FcF9F6')
        self.figureBinned.ax = self.figureBinned.add_subplot(111)
        self.canvas = FigureCanvas(self.figureBinned)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout_plot_data.addWidget(self.canvas)
        self.layout_plot_data.addWidget(self.toolbar)
        self.canvas.draw()


    def select_working_folder(self):
        self.working_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a folder", self.working_folder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        if self.working_folder:

            self.settings.setValue('working_folder', self.working_folder)
            if len(self.working_folder) > 50:
                self.label_working_folder.setText(self.working_folder[1:20] + '...' + self.working_folder[-30:])
            else:
                self.label_working_folder.setText(self.working_folder)
            self.get_file_list()

    def get_file_list(self):
        if self.working_folder:
            print('aaaaaa')
            self.list_data.clear()

            files_bin = [f for f in os.listdir(self.working_folder) if f.endswith('.dat')]

            if self.comboBox_sort_files_by.currentText() == 'Name':
                files_bin.sort()
            elif self.comboBox_sort_files_by.currentText() == 'Time':
                files_bin.sort(key=lambda x: os.path.getmtime('{}/{}'.format(self.working_folder, x)))

                files_bin.reverse()
            self.list_data.addItems(files_bin)

    def select_files_to_plot(self):
        df, header = load_binned_df_from_file(f'{self.working_folder}/{self.list_data.currentItem().text()}')
        keys = df.keys()
        refined_keys = []
        for key in keys:
            if not (('timestamp' in key) or ('energy' in key)):
                refined_keys.append(key)
        self.keys = refined_keys
        if self.keys != self.last_keys:
            self.list_xas_data_numerator.clear()
            self.list_xas_data_denominator.clear()
            self.list_xas_data_numerator.insertItems(0, self.keys)
            self.list_xas_data_denominator.insertItems(0, self.keys)
            if self.last_num != '' and self.last_num <= len(self.keys) - 1:
                self.list_xas_data_numerator.setCurrentRow(self.last_num)
            if self.last_den != '' and self.last_den <= len(self.keys) - 1:
                self.list_xas_data_denominator.setCurrentRow(self.last_den)

    def plot_xas_data(self):
        selected_items = (self.list_data.selectedItems())
        self.figureBinned.ax.clear()
        self.toolbar.update()
        self.figureBinned.ax.grid(alpha=0.4)
        # self.toolbar._views.clear()
        # self.toolbar._positions.clear()
        # self.toolbar._update_view()
        self.canvas.draw_idle()
        if self.list_xas_data_numerator.currentRow() == -1 or self.list_xas_data_denominator.currentRow() == -1:
            message_box('Warning','Please select numerator and denominator')
            return

        self.last_num = self.list_xas_data_numerator.currentRow()
        self.last_den = self.list_xas_data_denominator.currentRow()

        energy_key = 'energy'

        handles = []

        for i in selected_items:
            path = f'{self.working_folder}/{i.text()}'
            print(path)
            df, header = load_binned_df_from_file(path)
            numer = np.array(df[self.list_xas_data_numerator.currentItem().text()])
            denom = np.array(df[self.list_xas_data_denominator.currentItem().text()])
            if self.checkBox_ratio.checkState():
                y_label = (f'{self.list_xas_data_numerator.currentItem().text()} / '
                           f'{self.list_xas_data_denominator.currentItem().text()}')
                spectrum = numer/denom
            else:
                y_label = (f'{self.list_xas_data_numerator.currentItem().text()}')
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


    def add_files_to_xas_project(self):
        if self.list_xas_data_numerator.currentRow() != -1 and self.list_xas_data_denominator.currentRow() != -1:
            for item in self.list_data.selectedItems():
                filepath = str(Path(self.working_folder) / Path(item.text()))

                name = Path(filepath).resolve().stem
                df, header = load_binned_df_from_file(filepath)
                uid = header[header.find('UID:')+5:header.find('\n', header.find('UID:'))]


                try:
                    md = self.db[uid]['start']
                except:
                    print('Metadata not found')
                    md={}

                df = df.sort_values('energy')
                num_key = self.list_xas_data_numerator.currentItem().text()
                den_key = self.list_xas_data_denominator.currentItem().text()
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



