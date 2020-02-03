import os
import matplotlib.patches as mpatches
import numpy as np
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
from isstools.elements.figure_update import update_figure

from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file
from isstools.xasproject.xasproject import XASDataSet

if platform == 'darwin':
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview_project-mac.ui')
else:
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview_project.ui')


class UIXviewProject(*uic.loadUiType(ui_path)):
        def __init__(self, parent=None,*args, **kwargs):

            super().__init__(*args, **kwargs)
            self.setupUi(self)
            self.parent = parent
            self.parent.project.datasets_changed.connect(self.update_project_list)
            self.addCanvas()
            self.label_E0.setText("E<sub>0</sub>")
            self.list_project.itemSelectionChanged.connect(self.show_ds_params)
            self.list_project.setContextMenuPolicy(Qt.CustomContextMenu)
            self.list_project.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            self.list_project.customContextMenuRequested.connect(self.xas_project_context_menu)
            self.push_plot_project_in_E.clicked.connect(self.plot_project_in_E)
            self.push_plot_project_in_K.clicked.connect(self.plot_project_in_K)
            self.push_plot_project_in_R.clicked.connect(self.plot_project_in_R)



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

            # Menu defs
            # self.action_exit.triggered.connect(self.close_app)
            # self.action_save_project.triggered.connect(self.save_xas_project)
            # self.action_open_project.triggered.connect(self.open_xas_project)
            # self.action_save_datasets_as_text.triggered.connect(self.save_xas_datasets_as_text)
            # self.action_combine_and_save_as_text.triggered.connect(self.combine_and_save_datasets_as_text)
            # self.action_merge.triggered.connect(self.merge_datasets)
            # self.action_rename.triggered.connect(self.rename_dataset)
            # self.action_remove.triggered.connect(self.remove_from_xas_project)

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
                'pushButton_e0_set': 'lineEdit_e0',
                'pushButton_preedge_lo_set':    'lineEdit_preedge_lo',
                'pushButton_preedge_hi_set':    'lineEdit_preedge_hi',
                'pushButton_postedge_lo_set':   'lineEdit_postedge_lo',
                'pushButton_postedge_hi_set':   'lineEdit_postedge_hi',
                'pushButton_spline_lo_set':     'lineEdit_spline_lo',
                'pushButton_spline_hi_set':     'lineEdit_spline_hi',
                'pushButton_k_ft_lo_set':       'lineEdit_k_ft_lo',
                'pushButton_k_ft_hi_set':       'lineEdit_k_ft_hi',
                'pushButton_truncate_at_set':   'lineEdit_truncate_at'
            }
            self.windows_list = [
                'hanning',
                'kaiser',
                'gaussian',
                'sine'
            ]

        def xas_project_context_menu(self, QPos):
            menu = QMenu()
            rename_action = menu.addAction("&Rename")
            merge_action = menu.addAction("&Merge")
            remove_action = menu.addAction("&Remove")
            save_datasets_as_text_action = menu.addAction("&Save datasets as text")
            combine_and_save_datasets_as_text_action = menu.addAction("&Combine and save datasets as text")
            parentPosition = self.list_project.mapToGlobal(QtCore.QPoint(0, 0))
            menu.move(parentPosition + QPos)
            action = menu.exec_()
            if action == rename_action:
                self.rename_dataset()
            elif action == merge_action:
                self.merge_datasets()
            elif action == remove_action:
                self.remove_from_xas_project()
            elif action == combine_and_save_datasets_as_text_action:
                self.combine_and_save_datasets_as_text()
            elif action == save_datasets_as_text_action:
                self.save_datasets_as_text()


        def addCanvas(self):
            # XASProject Plot:
            self.figure_project = Figure()
            #self.figure_project.set_facecolor(color='#E2E2E2')
            self.figure_project.ax = self.figure_project.add_subplot(111)
            self.figure_project.ax.grid(alpha=0.4)
            self.canvas_project = FigureCanvas(self.figure_project)

            self.toolbar_project = NavigationToolbar(self.canvas_project, self)
            self.layout_plot_project.addWidget(self.canvas_project)
            self.layout_plot_project.addWidget(self.toolbar_project)
            self.figure_project.tight_layout()

            self.canvas_project.draw()
            # layout_plot_xasproject

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
            self.ft_param_list = [

            ]
            selection = self.list_project.selectedIndexes()
            if selection != []:
                sender = QObject()
                sender_object = sender.sender().objectName()
                index = selection[0].row()
                ds_master = self.parent.project[index]
                if sender_object == 'pushButton_push_norm_param_to_selected':
                    for indx, obj in enumerate(selection):
                        ds = self.parent.project[selection[indx].row()]
                        for param in self.norm_param_list:
                            setattr(ds, param, getattr(ds_master, param))
                if sender_object == 'pushButton_push_norm_param_to_all':
                    for indx, obj in enumerate(self.parent.project):
                        for param in self.norm_param_list:
                            setattr(self.parent.project[indx], param, getattr(ds_master, param))
                if sender_object == 'pushButton_push_bkg_param_to_selected':
                    for indx, obj in enumerate(selection):
                        ds = self.parent.project[selection[indx].row()]
                        for param in self.bkg_param_list:
                            setattr(ds, param, getattr(ds_master, param))
                if sender_object == 'pushButton_push_bkg_param_to_all':
                    for indx, obj in enumerate(self.parent.project):
                        for param in self.bkg_param_list:
                            setattr(self.parent.project[indx], param, getattr(ds_master, param))

        # here we begin to work on the second pre-processing tab
        def update_ds_params(self):
            sender = QObject()
            sender_object = sender.sender().objectName()
            print(sender_object)
            selection = self.list_project.selectedIndexes()
            if selection != []:
                index = selection[0].row()
                ds = self.parent.xasproject[index]
                try:
                    self.statusBar().showMessage(sender_object)
                    print(getattr(self, sender_object).text())
                    setattr(ds, self.lineEdit_to_ds_parameter_dict[sender_object],
                            float(getattr(self, sender_object).text()))
                except:
                    self.statusBar().showMessage('Use numbers only')

        def set_ds_params_from_plot(self):
            sender = QObject()
            self.sender_object = sender.sender().objectName()
            self.statusBar().showMessage('Click on graph or press Esc')
            self.cid = self.canvas_project.mpl_connect('button_press_event', self.mouse_press_event)

        def _disconnect_cid(self):
            if hasattr(self, 'cid'):
                self.canvas_project.mpl_disconnect(self.cid)
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

            lineEdit = getattr(self, self.pushButton_set_to_lineEdit_dict[self.sender_object])
            e0 = float(self.lineEdit_e0.text())
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
                new_value = event.xdata - e0

            lineEdit.setText('{:.1f}'.format(new_value))
            sender_object = lineEdit

            print(sender_object)
            selection = self.list_project.selectedIndexes()
            if selection != []:
                index = selection[0].row()
                ds = self.parent.project[index]
                try:
                    float(sender_object.text())
                    setattr(ds, self.lineEdit_to_ds_parameter_dict[sender_object.objectName()],
                            float(sender_object.text()))
                except:
                    print('what''s going wrong')

            self._disconnect_cid()

        def update_project_list(self, datasets):
            self.list_project.clear()
            for ds in datasets:
                self.list_project.addItem(ds.name)


        def show_ds_params(self):
            print('12')
            if self.list_project.selectedIndexes():
                index = self.list_project.selectedIndexes()[0]
                ds = self.parent.project[index.row()]
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

                for i in range(self.list_project.count()):
                    self.list_project.item(i).setFont(font)
                font.setBold(True)
                self.list_project.item(index.row()).setFont(font)

        def remove_from_xas_project(self):
            for index in self.list_project.selectedIndexes()[
                         ::-1]:  # [::-1] to remove using indexes from last to first
                self.parent.project.removeDatasetIndex(index.row())
                self.statusBar().showMessage('Datasets deleted')

        def plot_project_in_E(self):
            if self.list_project.selectedIndexes():
                update_figure([self.figure_project.ax], self.toolbar_project, self.canvas_project)

                for index in self.list_project.selectedIndexes():
                    ds = self.parent.project[index.row()]
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
                    self.figure_project.ax.plot(energy, data, label=ds.name)

                    if self.radioButton_mu_xasproject.isChecked() and not self.checkBox_deriv.isChecked():
                        if self.checkBox_preedge_show.checkState():
                            self.figure_project.ax.plot(ds.energy, ds.pre_edge, label='Preedge', linewidth=0.75)
                        if self.checkBox_postedge_show.checkState():
                            self.figure_project.ax.plot(ds.energy, ds.post_edge, label='Postedge', linewidth=0.75)
                        if self.checkBox_background_show.checkState():
                            self.figure_project.ax.plot(ds.energy, ds.bkg, label='Background', linewidth=0.75)

                self.parent.set_figure(self.figure_project.ax, self.canvas_project, label_x='Energy /eV',
                                label_y=r'$\chi  \mu$' + '(E)'),

                if self.checkBox_force_range_E.checkState():
                    self.figure_project.ax.set_xlim(
                        (float(self.lineEdit_e0.text()) + float(self.lineEdit_range_E_lo.text())),
                        (float(self.lineEdit_e0.text()) + float(self.lineEdit_range_E_hi.text())))
                self.current_plot_in = 'e'

        def plot_project_in_K(self):
            if self.list_project.selectedIndexes():
                update_figure([self.figure_project.ax], self.toolbar_project, self.canvas_project)
                window = self.set_ft_window()
                for index in self.list_project.selectedIndexes():
                    ds = self.parent.project[index.row()]
                    ds.extract_chi_force()
                    ds.extract_ft_force(window=window)

                    data = ds.chi * np.power(ds.k, self.spinBox_k_weight.value())

                    self.figure_project.ax.plot(ds.k, data, label=ds.name)
                    data_max = data.max()
                    if self.checkBox_show_window.isChecked():
                        self.figure_project.ax.plot(ds.k, ds.kwin * data_max / 2, label='Windows')

                self.parent.set_figure(self.figure_project.ax, self.canvas_project,
                                label_x='k (' + r'$\AA$' + '$^1$' + ')',
                                label_y=r'$\chi  \mu$' + '(k)')

                if self.checkBox_force_range_k.checkState():
                    self.figure_project.ax.set_xlim(float(self.lineEdit_range_k_lo.text()),
                                                      float(self.lineEdit_range_k_hi.text()))
                self.current_plot_in = 'k'

        def plot_project_in_R(self):
            if self.list_project.selectedIndexes():
                update_figure([self.figure_project.ax], self.toolbar_project, self.canvas_project)
                window = self.set_ft_window()
                for index in self.list_project.selectedIndexes():
                    ds = self.parent.project[index.row()]
                    ds.extract_ft_force(window=window)
                    if self.checkBox_show_chir_mag.checkState():
                        self.figure_project.ax.plot(ds.r, ds.chir_mag, label=ds.name)
                    if self.checkBox_show_chir_im.checkState():
                        self.figure_project.ax.plot(ds.r, ds.chir_im, label=(ds.name + ' Im'))
                    if self.checkBox_show_chir_re.checkState():
                        self.figure_project.ax.plot(ds.r, ds.chir_re, label=(ds.name + ' Re'))
                    # if self.checkBox_show_chir_pha.checked:
                    #    self.figure_project.ax.plot(ds.r, ds.chir_pha, label=(ds.name + ' Ph'))

                self.parent.set_figure(self.figure_project.ax, self.canvas_project, label_y=r'$\chi  \mu$' + '(k)',
                                label_x='R (' + r'$\AA$' + ')')
                if self.checkBox_force_range_R.checkState():
                    self.figure_project.ax.set_xlim(float(self.lineEdit_range_R_lo.text()),
                                                      float(self.lineEdit_range_R_hi.text()))
                self.current_plot_in = 'R'

        def save_xas_project(self):
            options = QtWidgets.QFileDialog.DontUseNativeDialog
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project as', self.parent.widget_data.working_folder,
                                                                'XAS project files (*.xas)', options=options)
            if filename:
                if Path(filename).suffix != '.xas':
                    filename = filename + '.xas'
                print(filename)
                self.parent.project.save(filename=filename)

        def open_xas_project(self):
            options = QtWidgets.QFileDialog.DontUseNativeDialog
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load XAS project', self.parent.widget_data.working_folder,
                                                                'XAS project files (*.xas)', options=options)
            if filename:
                self.parent.project_loaded_from_file = xasproject.XASProject()
                self.parent.project_loaded_from_file.load(filename=filename)

                if ret == 0:
                    self.parent.project = self.parent.xasproject_loaded_from_file
                    self.update_project_list(self.parent.project._datasets)
                if ret == 1:
                    for i in self.parent.project_loaded_from_file._datasets:
                        self.parent.project.append(i)

        def save_datasets_as_text(self):
            # options = QtWidgets.QFileDialog.DontUseNativeDialog
            # filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project as', self.parent.widget_data.working_folder,
            #                                          'XAS project files (*.xas)', options=options)
            selection = self.list_project.selectedIndexes()
            if selection != []:
                ret = self.message_box_save_datasets_as()
                options = QtWidgets.QFileDialog.DontUseNativeDialog
                pathname = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose folder...',
                                                                      self.parent.widget_data.working_folder,
                                                                      options=options)
                separator = '#______________________________________________________\n'
                if pathname is not '':
                    for indx, obj in enumerate(selection):
                        ds = self.parent.project._datasets[selection[indx].row()]
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

                        filename_new = '{}/{}.{}'.format(pathname, filename, 'mu')
                        fid = open(filename_new, 'w')
                        header_wo_cols_names = ds.header[0:ds.header.rfind('#')]
                        fid.write(header_wo_cols_names)
                        fid.write(separator)
                        fid.write(keys)
                        fid.close()

                        fid = open(filename_new, 'a')
                        np.savetxt(fid, table)
                        fid.close()

        def merge_datasets(self):
            selection = self.list_project.selectedIndexes()
            if selection != []:

                mu = self.parent.project._datasets[selection[0].row()].mu
                energy_master = self.parent.project._datasets[selection[0].row()].energy
                mu_array = np.zeros([len(selection), len(mu)])
                energy = self.parent.project._datasets[selection[0].row()].energy
                md = ['# merged \n']
                for indx, obj in enumerate(selection):
                    energy = self.parent.project._datasets[selection[indx].row()].energy
                    mu = self.parent.project._datasets[selection[indx].row()].mu.mu
                    mu = np.interp(energy_master, energy, mu)
                    mu_array[indx, :] = mu
                    md.append('# ' + self.parent.project._datasets[selection[indx].row()].filename + '\n')

                mu_merged = np.average(mu_array, axis=0)
                merged = XASDataSet(name='merge', md=md, energy=energy, mu=mu_merged, filename='',
                                               datatype='processed')
                merged.header = "".join(merged.md)
                self.parent.project.append(merged)
                self.parent.project.project_changed()

        def combine_and_save_datasets_as_text(self):
            selection = self.list_project.selectedIndexes()
            if selection != []:
                ds_list = []
                md = []
                for indx, obj in enumerate(selection):
                    ds_list.append(self.parent.project._datasets[selection[indx].row()])

                ds_list.sort(key=lambda x: x.name)
                mu = ds_list[0].mu
                mu_array = np.zeros([len(selection) + 1, len(mu)])
                energy_master = ds_list[0].energy

                mu_array[0, :] = energy_master
                ret = self.message_box_save_datasets_as()
                for indx, obj in enumerate(selection):
                    ds = ds_list[indx]
                    energy = ds.energy
                    if ret == 0:
                        yy = np.array(ds.mu.mu)
                        keys = '# energy(eV), mu(E)\n'
                    elif ret == 1:
                        yy = ds.norm
                        keys = '# energy(eV), normalized mu(E)\n'
                    elif ret == 2:
                        yy = ds.flat
                        keys = '# energy(eV), flattened normalized mu(E)\n'

                    yy = np.interp(energy_master, energy, yy)
                    mu_array[indx + 1, :] = yy
                    md.append(ds.name)

                self.mu_array = mu_array
                options = QtWidgets.QFileDialog.DontUseNativeDialog
                filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save XAS project', self.parent.widget_data.working_folder,
                                                                    'XAS dataset (*.dat)', options=options)
                if filename:
                    if Path(filename).suffix != '.xas':
                        filename = filename + '.xas'
                    print(filename)
                    filelist = "{}".format("\n".join(md[0:]))
                    separator = '\n #______________________________________________________\n'

                    header = '{} {} {}'.format(filelist, separator, keys)
                    fid = open(filename, 'w')
                    np.savetxt(fid, np.transpose(mu_array), header=header)
                    fid.close()

        def rename_dataset(self):
            selection = self.list_project.selectedIndexes()
            if selection != []:
                name = self.parent.project._datasets[selection[0].row()].name
                new_name, ok = QtWidgets.QInputDialog.getText(self, 'Rename dataset', 'Enter new name:',
                                                              QtWidgets.QLineEdit.Normal, name)
                if ok:
                    self.parent.project._datasets[selection[0].row()].name = new_name
                    self.parent.project.project_changed()

        def truncate(self):
            sender = QObject()
            sender_object = sender.sender().objectName()
            print(sender_object)
            selection = self.list_project.selectedIndexes()
            if selection != []:
                for indx, obj in enumerate(selection):
                    print(indx)
                    ds = self.parent.project._datasets[selection[indx].row()]
                    print(ds.name)
                    energy = ds.energy
                    mu = ds.mu
                    indx_energy_to_truncate_at = (np.abs(energy - float(self.lineEdit_truncate_at.text()))).argmin()

                    if sender_object == 'pushButton_truncate_below':
                        ds.energy = energy[indx_energy_to_truncate_at:]
                        ds.mu = mu[indx_energy_to_truncate_at:]

                    elif sender_object == 'pushButton_truncate_above':
                        ds.energy = energy[0:indx_energy_to_truncate_at]

                        ds.mu = mu[0:indx_energy_to_truncate_at:]
                    ds.update_larch()
                    self.parent.project._datasets[selection[indx].row()] = ds

        '''
         Service routines
        '''

        def message_box_save_datasets_as(self):
            messageBox = QtWidgets.QMessageBox()
            messageBox.setText('Save datasets as..')
            messageBox.addButton(QtWidgets.QPushButton('mu(E)'), QtWidgets.QMessageBox.YesRole)
            messageBox.addButton(QtWidgets.QPushButton('normalized mu(E)'), QtWidgets.QMessageBox.NoRole)
            messageBox.addButton(QtWidgets.QPushButton('flattened mu(E)'), QtWidgets.QMessageBox.NoRole)
            ret = messageBox.exec_()
            return ret

        def message_box_warning(self, line1='Warning', line2=''):

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


