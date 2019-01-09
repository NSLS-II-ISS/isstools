import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import numpy as np
import warnings
from ophyd import utils as ophyd_utils


import os

from isstools.conversions import xray
from isstools.elements.figure_update import update_figure
from isstools.dialogs.BasicDialogs import question_message_box

from xas.file_io import load_interpolated_df_from_file
from xas.bin import bin

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_processing.ui')



class UIProcessing(*uic.loadUiType(ui_path)):
    def __init__(self,
                 hhm,
                 db,
                 parent_gui,
                 *args, **kwargs):
        '''
            hhm:
                the monochromator
            db : the data database
            det_dict:
                detector dictionary
            parent_gui:
                the parent gui

        '''
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()


        self.hhm = hhm
        self.db = db

        self.settings = QSettings(parent_gui.window_title, 'XLive')
        self.edit_E0.setText(self.settings.value('e0_processing', defaultValue='11470', type=str))
        self.edit_E0.textChanged.connect(self.save_e0_processing_value)
        self.user_dir = self.settings.value('user_dir', defaultValue = '/GPFS/xf08id/users/', type = str)

        # Initialize 'processing' tab
        self.push_select_file.clicked.connect(self.select_files_to_bin)
        self.push_bin.clicked.connect(self.bin_selected_files)
        self.push_save_binned.clicked.connect(self.save_binned)
        self.push_calibrate.clicked.connect(self.calibrate_offset)
        self.push_replot_file.clicked.connect(self.replot)
        self.push_reset_data.clicked.connect(self.reset_data_plots)
        self.cid = self.canvas_interpolated_scans.mpl_connect('button_press_event', self.getX)
        self.edge_found = -1
        # Disable buttons
        self.push_bin.setDisabled(True)
        self.push_replot_file.setDisabled(True)
        self.plotting_list = []
        self.last_num = ''
        self.last_den = ''
        self.last_num_text = 'i0'
        self.last_den_text = 'it'
        self.binned_datasets = []
        self.interpolated_datasets = []
        self.interpolated_headers = []

    def addCanvas(self):
        self.figure_interpolated_scans = Figure()
        self.figure_interpolated_scans.set_facecolor(color='#FcF9F6')
        self.canvas_interpolated_scans = FigureCanvas(self.figure_interpolated_scans)
        self.figure_interpolated_scans.ax = self.figure_interpolated_scans.add_subplot(111)
        self.toolbar_interpolated_scans = NavigationToolbar(self.canvas_interpolated_scans, self, coordinates=True)
        self.plot_interpolated_scans.addWidget(self.toolbar_interpolated_scans)
        self.plot_interpolated_scans.addWidget(self.canvas_interpolated_scans)
        self.canvas_interpolated_scans.draw_idle()
        self.figure_interpolated_scans.ax.grid(alpha = 0.4)
        self.figure_binned_scans = Figure()
        self.figure_binned_scans.set_facecolor(color='#FcF9F6')
        self.canvas_binned_scans = FigureCanvas(self.figure_binned_scans)
        self.figure_binned_scans.ax = self.figure_binned_scans.add_subplot(111)
        self.toolbar_binned_scans = NavigationToolbar(self.canvas_binned_scans, self, coordinates=True)
        self.plot_binned_scans.addWidget(self.toolbar_binned_scans)
        self.plot_binned_scans.addWidget(self.canvas_binned_scans)
        self.canvas_binned_scans.draw_idle()
        self.figure_binned_scans.ax.grid(alpha=0.4)

    def getX(self, event):
        if event.button == 3:
            ret = question_message_box(self,
                                       'Setting edge position',
                                       'Would you like to set the edge to {:.0f}?'.format(event.xdata))
            if ret:
                self.edit_E0.setText(str(int(np.round(event.xdata))))

    def set_new_angle_offset(self, value):
        try:
            self.hhm.angle_offset.put(float(value))
        except Exception as exc:
            if type(exc) == ophyd_utils.errors.LimitError:
                print('[New offset] {}. No reason to be desperate, though.'.format(exc))
            else:
                print('[New offset] Something went wrong, not the limit: {}'.format(exc))
            return 1
        return 0

    def save_e0_processing_value(self, string):
        self.settings.setValue('e0_processing', string)

    def select_files_to_bin(self):
        if self.checkBox_process_bin.checkState():
            self.list_files_to_bin = QtWidgets.QFileDialog.getOpenFileNames(directory = self.user_dir,
                                                               filter = '*.raw', parent = self)[0]
            single_file = False
        else:
            single_file = True
            self.list_files_to_bin = QtWidgets.QFileDialog.getOpenFileName(directory = self.user_dir,
                                                               filter = '*.raw', parent = self)[0]
            if len(self.list_files_to_bin) > 0:
                self.list_files_to_bin=[self.list_files_to_bin]
            else:
                self.list_files_to_bin=[]

        if self.list_files_to_bin:
            (path, filename) = os.path.split(self.list_files_to_bin[0])
            self.settings.setValue('user_dir', path)
            self.interpolated_datasets = []
            self.interpolated_headers = []
            self.binned_datasets = []
            self.filenames = []
            for file_to_bin in self.list_files_to_bin:
                (path, filename) = os.path.split(file_to_bin)
                self.filenames.append(filename)
                self.push_bin.setEnabled(True)
                self.push_save_binned.setEnabled(True)
                (dataset, header) = load_interpolated_df_from_file(file_to_bin)
                self.interpolated_headers.append(header)
                self.interpolated_datasets.append(dataset)
            self.label_filenames.setText(' '.join(self.filenames))
            if single_file:
                self.plot_interpolated_datasets()
            else:
                self.plot_interpolated_datasets()

    def plot_interpolated_datasets(self):
        keys=self.interpolated_datasets[0].keys()
        self.create_lists(keys, keys)
        self.update_list_widgets()
        self.erase_plots()
        for dataset in self.interpolated_datasets:
            if self.checkBox_ratio.isChecked():
                result = dataset[self.last_num_text] / dataset[self.last_den_text]
                ylabel = f'{self.last_num_text} / {self.last_den_text}'
            else:
                result = dataset[self.last_num_text]
                ylabel = f'{self.last_num_text}'
            if self.checkBox_log.checkState():
                result = np.log(result)
            if self.checkBox_neg.checkState():
                result = -result
            self.figure_interpolated_scans.ax.plot(dataset['energy'], result)
            self.figure_interpolated_scans.ax.set_ylabel(ylabel)
            self.figure_interpolated_scans.ax.set_xlabel('Energy /eV')
            self.figure_interpolated_scans.tight_layout()
            self.canvas_interpolated_scans.draw_idle()
        self.push_replot_file.setEnabled(True)

    def replot(self):
        self.erase_plots()
        if self.listWidget_numerator.currentRow() is not -1:
            self.last_num_text = self.listWidget_numerator.currentItem().text()
        if self.listWidget_denominator.currentRow() is not -1:
            self.last_den_text = self.listWidget_denominator.currentItem().text()
        self.plot_interpolated_datasets()
        self.plot_binned_datasets()

    def update_list_widgets(self):
        index = [index for index, item in enumerate(
            [self.listWidget_numerator.item(index) for index in range(self.listWidget_numerator.count())]) if
                 item.text() == self.last_num_text]
        if len(index):
            self.listWidget_numerator.setCurrentRow(index[0])
        else:
            self.listWidget_numerator.setCurrentRow(0)

        index = [index for index, item in enumerate(
            [self.listWidget_denominator.item(index) for index in range(self.listWidget_denominator.count())]) if
                 item.text() == self.last_den_text]
        if len(index):
            self.listWidget_denominator.setCurrentRow(index[0])
        else:
            self.listWidget_denominator.setCurrentRow(0)

    def create_lists(self, list_num, list_den):
        self.listWidget_numerator.clear()
        self.listWidget_denominator.clear()
        self.listWidget_numerator.insertItems(0, list_num)
        self.listWidget_denominator.insertItems(0, list_den)

    def bin_selected_files(self):
        self.binned_datasets = []
        if len(self.interpolated_datasets) > 0:
            e0 = int(self.edit_E0.text())
            edge_start = int(self.edit_edge_start.text())
            edge_end = int(self.edit_edge_end.text())
            preedge_spacing = float(self.edit_preedge_spacing.text())
            xanes_spacing = float(self.edit_xanes_spacing.text())
            exafs_spacing = float(self.edit_exafs_spacing.text())
            for dataset in self.interpolated_datasets:
                binned_dataset = bin(dataset, e0=e0, edge_start=edge_start,
                                      edge_end=edge_end, preedge_spacing=preedge_spacing,
                                      xanes_spacing=xanes_spacing, exafs_k_spacing=exafs_spacing)

                self.binned_datasets.append(binned_dataset)
            self.plot_binned_datasets()


    def plot_binned_datasets(self):
        update_figure([self.figure_binned_scans.ax], self.toolbar_binned_scans,
                      self.canvas_binned_scans)
        for dataset in self.binned_datasets:
            if self.checkBox_ratio.isChecked():
                result = dataset[self.last_num_text] / dataset[self.last_den_text]
                ylabel = f'{self.last_num_text} / {self.last_den_text}'
            else:
                result = dataset[self.last_num_text]
                ylabel = f'{self.last_num_text}'
            if self.checkBox_log.checkState():
                result = np.log(result)
            if self.checkBox_neg.checkState():
                result = -result
            self.figure_binned_scans.ax.plot(dataset['energy'], result)
            self.figure_binned_scans.ax.set_ylabel(ylabel)
            self.figure_binned_scans.ax.set_xlabel('Energy /eV')
            self.figure_binned_scans.tight_layout()
            self.canvas_binned_scans.draw_idle()
        self.push_replot_file.setEnabled(True)



    def save_binned(self):
        filename = self.curr_filename_save
        self.gen_parser.data_manager.export_dat(filename)
        print('[Save File] File Saved! [{}]'.format(filename[:-3] + 'dat'))

    def calibrate_offset(self):
        ret = self.questionMessage('Confirmation', 'Are you sure you would like to calibrate it?')
        if not ret:
            print('[E0 Calibration] Aborted!')
            return False

        new_value = str(self.hhm.angle_offset.value - (xray.energy2encoder(float(self.edit_E0.text()),
                   self.hhm.pulses_per_deg) - xray.energy2encoder(float(self.edit_ECal.text()), self.hhm.pulses_per_deg))/self.hhm.pulses_per_deg)
        if self.set_new_angle_offset(new_value):
            return
        print ('[E0 Calibration] New value: {}\n[E0 Calibration] Completed!'.format(new_value))

    def plot_data(self, data):
        df = data['processing_ret']['data']
        if isinstance(df, str):
            # load data, it's  astring
            df = self.gen_parser.getInterpFromFile(df)
        #df = pd.DataFrame.from_dict(json.loads(data['processing_ret']['data']))
        df = df.sort_values('energy')
        self.df = df
        self.bin_data_sets.append(data)
        self.create_lists(df.keys(), df.keys())
        self.update_listWidgets()
        self.push_replot_file.setEnabled(True)

        division = df[self.last_num_text] / df[self.last_den_text]

        if self.checkBox_log.checkState() > 0:
            division[division < 0] = 1
            division = np.log(division)

        if self.checkBox_neg.checkState() > 0:
            division = -division

        self.figure_binned_scans.ax.plot(df['energy'], division)

        last_trace = self.figure_binned_scans.ax.get_lines()[len(self.figure_binned_scans.ax.get_lines()) - 1]
        patch = mpatches.Patch(color=last_trace.get_color(), label=data['processing_ret']['metadata']['name'])
        self.handles_bin.append(patch)

        self.figure_binned_scans.ax.legend(handles=self.handles_bin)
        self.canvas_binned_scans.draw_idle()

    def erase_plots(self):
        update_figure([self.figure_interpolated_scans.ax], self.toolbar_interpolated_scans,
                      self.canvas_interpolated_scans)
        update_figure([self.figure_binned_scans.ax], self.toolbar_binned_scans,
                      self.canvas_binned_scans)

    def reset_data_plots(self):
        self.push_replot_file.setEnabled(False)
        self.listWidget_numerator.clear()
        self.listWidget_denominator.clear()
        self.bin_data_sets = []
        self.interp_data_sets = []
        self.handles_interp = []
        self.handles_bin = []
        self.erase_plots()

