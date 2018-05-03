import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import numpy as np
import collections
import time as ttime
import warnings
from ophyd import utils as ophyd_utils
import pandas as pd
import json
import socket

from isstools.xasdata import xasdata
from isstools.conversions import xray

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_processing.ui')

# Things for the ZMQ communication
import socket


from bluesky.callbacks import CallbackBase


class UIProcessing(*uic.loadUiType(ui_path)):
    def __init__(self,
                 hhm,
                 db,
                 det_dict, parent_gui,
                 job_submitter,
                 *args, **kwargs):
        '''
            hhm:
                the monochromator
            db : the data database
            det_dict:
                detector dictionary
            parent_gui:
                the parent gui
            job_submitter: function
                the function that submits jobs for processing
                takes uid as argument only (pass the rest through functools.partial)
        '''
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.job_submitter = job_submitter

        self.hhm = hhm
        self.db = db
        self.det_dict = det_dict
        self.gen_parser = xasdata.XASdataGeneric(self.hhm.enc.pulses_per_deg, self.db)

        self.settings = QSettings(parent_gui.window_title, 'XLive')
        self.edit_E0_2.setText(self.settings.value('e0_processing', defaultValue='11470', type=str))
        self.edit_E0_2.textChanged.connect(self.save_e0_processing_value)
        self.user_dir = self.settings.value('user_dir', defaultValue = '/GPFS/xf08id/users/', type = str)

        # Initialize 'processing' tab
        self.push_select_file.clicked.connect(self.selectFile)
        self.push_bin_save.clicked.connect(self.bin_single_data)
        self.push_calibrate.clicked.connect(self.calibrate_offset)
        self.push_replot_file.clicked.connect(self.replot_data)
        self.push_reset_data.clicked.connect(self.reset_data_plots)
        self.cid = self.canvas_old_scans_2.mpl_connect('button_press_event', self.getX)
        self.edge_found = -1
        # Disable buttons
        self.push_bin_save.setDisabled(True)
        self.push_replot_file.setDisabled(True)
        self.active_threads = 0
        self.total_threads = 0
        self.plotting_list = []
        self.last_num = ''
        self.last_den = ''
        self.last_num_text = 'i0'
        self.last_den_text = 'it'
        self.bin_data_sets = []
        self.interp_data_sets = []
        self.handles_interp = []
        self.handles_bin = []

    def addCanvas(self):

        self.figure_old_scans_2 = Figure()
        self.figure_old_scans_2.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans_2 = FigureCanvas(self.figure_old_scans_2)
        self.figure_old_scans_2.ax = self.figure_old_scans_2.add_subplot(111)
        self.figure_old_scans_2.ax2 = self.figure_old_scans_2.ax.twinx()
        self.toolbar_old_scans_2 = NavigationToolbar(self.canvas_old_scans_2, self, coordinates=True)
        self.plot_old_scans_2.addWidget(self.toolbar_old_scans_2)
        self.plot_old_scans_2.addWidget(self.canvas_old_scans_2)
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3 = Figure()
        self.figure_old_scans_3.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans_3 = FigureCanvas(self.figure_old_scans_3)
        self.figure_old_scans_3.ax = self.figure_old_scans_3.add_subplot(111)
        self.figure_old_scans_3.ax2 = self.figure_old_scans_3.ax.twinx()
        self.toolbar_old_scans_3 = NavigationToolbar(self.canvas_old_scans_3, self, coordinates=True)
        self.plot_old_scans_3.addWidget(self.toolbar_old_scans_3)
        self.plot_old_scans_3.addWidget(self.canvas_old_scans_3)
        self.canvas_old_scans_3.draw_idle()

    def getX(self, event):
        if event.button == 3:
            ret = self.questionMessage('Setting Edge', 'Would like to set the edge to {:.0f}?'.format(event.xdata))
            if ret:
                self.edit_E0_2.setText(str(int(np.round(event.xdata))))

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

    def selectFile(self):
        if self.checkBox_process_bin.checkState() > 0:
            self.selected_filename_bin = QtWidgets.QFileDialog.getOpenFileNames(directory = self.user_dir, filter = '*.txt', parent = self)[0]
        else:
            self.selected_filename_bin = QtWidgets.QFileDialog.getOpenFileName(directory = self.user_dir, filter = '*.txt', parent = self)[0]
            if len(self.selected_filename_bin)>0:
                self.selected_filename_bin=[self.selected_filename_bin]
            else:
                self.selected_filename_bin=[]
        if len(self.selected_filename_bin):
            self.handles_interp = []
            self.handles_bin = []
            self.interp_data_sets = []
            self.bin_data_sets = []
            self.uids = []
            if len(self.selected_filename_bin) > 1:
                filenames = []
                self.user_dir = self.selected_filename_bin[0].rsplit('/', 1)[0]
                for name in self.selected_filename_bin:
                    filenames.append(name.rsplit('/', 1)[1])
                    self.uids.append(self.gen_parser.read_header(name).split('UID: ')[1].split('\n')[0])
                filenames = ', '.join(filenames)
                self.push_bin_save.setEnabled(False)
            elif len(self.selected_filename_bin) == 1:
                filenames = self.selected_filename_bin[0]
                self.user_dir = filenames.rsplit('/', 1)[0]
                self.uids.append(self.gen_parser.read_header(filenames).split('UID: ')[1].split('\n')[0])
                self.push_bin_save.setEnabled(True)

            print(self.uids)
            self.settings.setValue('user_dir', self.user_dir)
            self.label_24.setText(filenames)
            self.send_data_request()

    def update_listWidgets(self):
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

    def bin_single_data(self):
        for index, uid in enumerate(self.uids):
            self.send_bin_request(uid, filepath=self.selected_filename_bin[index])

    def send_bin_request(self, uid, filepath):
        e0 = int(self.edit_E0_2.text())
        edge_start = int(self.edit_edge_start.text())
        edge_end = int(self.edit_edge_end.text())
        preedge_spacing = float(self.edit_preedge_spacing.text())
        xanes_spacing = float(self.edit_xanes_spacing.text())
        exafs_spacing = float(self.edit_exafs_spacing.text())
        req = {'uid': uid,
               'requester': socket.gethostname(),
               'type': 'spectroscopy',
               'processing_info': {
                   'type': 'bin',
                   'filepath': filepath, #self.selected_filename_bin[index],
                   'e0': e0,
                   'edge_start': edge_start,
                   'edge_end': edge_end,
                   'preedge_spacing': preedge_spacing,
                   'xanes_spacing': xanes_spacing,
                   'exafs_spacing': exafs_spacing,
                }
               }
        self.job_submitter(req)




    def send_data_request(self):
        index = 1
        self.old_scans_control = 1
        self.old_scans_2_control = 1
        self.old_scans_3_control = 1

        self.figure_old_scans_2.ax.clear()
        self.figure_old_scans_2.ax2.clear()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        self.toolbar_old_scans_2._update_view()
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3.ax.clear()
        self.figure_old_scans_3.ax2.clear()
        self.toolbar_old_scans_3._views.clear()
        self.toolbar_old_scans_3._positions.clear()
        self.toolbar_old_scans_3._update_view()
        self.canvas_old_scans_3.draw_idle()

        # print('[Launching Threads]')
        if self.listWidget_numerator.currentRow() is not -1:
            self.last_num = self.listWidget_numerator.currentRow()
            self.last_num_text = self.listWidget_numerator.currentItem().text()
        if self.listWidget_denominator.currentRow() is not -1:
            self.last_den = self.listWidget_denominator.currentRow()
            self.last_den_text = self.listWidget_denominator.currentItem().text()
        self.listWidget_numerator.setCurrentRow(-1)
        self.listWidget_denominator.setCurrentRow(-1)

        for index, uid in enumerate(self.uids):
            req = {'uid': uid,
                   'requester': socket.gethostname(),
                   'type': 'spectroscopy',
                   'processing_info': {
                       'type': 'request_interpolated_data',
                       'filepath': self.selected_filename_bin[index],
                   }
                  }
            self.job_submitter(req)

            if self.checkBox_process_bin.checkState() > 0:
                self.send_bin_request(uid, self.selected_filename_bin[index])

    def save_bin(self):
        filename = self.curr_filename_save
        self.gen_parser.data_manager.export_dat(filename)
        print('[Save File] File Saved! [{}]'.format(filename[:-3] + 'dat'))

    def calibrate_offset(self):
        ret = self.questionMessage('Confirmation', 'Are you sure you would like to calibrate it?')
        if not ret:
            print('[E0 Calibration] Aborted!')
            return False

        new_value = str(self.hhm.angle_offset.value - (xray.energy2encoder(float(self.edit_E0_2.text()), self.hhm.pulses_per_deg) - xray.energy2encoder(float(self.edit_ECal.text()), self.hhm.pulses_per_deg))/self.hhm.pulses_per_deg)
        if self.set_new_angle_offset(new_value):
            return
        print ('[E0 Calibration] New value: {}\n[E0 Calibration] Completed!'.format(new_value))



    def replot_data(self):
        self.replot(self.bin_data_sets, self.handles_bin, self.figure_old_scans_3, self.toolbar_old_scans_3)
        self.replot(self.interp_data_sets, self.handles_interp, self.figure_old_scans_2, self.toolbar_old_scans_2)
        self.replot_y()

    def replot_y(self):
        #self.figure_old_scans.ax.clear()
        #self.figure_old_scans.canvas.draw_idle()
        #self.toolbar_old_scans._views.clear()
        #self.toolbar_old_scans._positions.clear()
        #self.toolbar_old_scans._update_view()

        for data in self.bin_data_sets:
            df = data['processing_ret']['data']
            #self.update_k_view(df)

    def replot(self, list_data_set, handles, figure, toolbar):
        figure.ax.clear()
        if hasattr(figure, 'ax2'):
            figure.ax2.clear()
        figure.canvas.draw_idle()
        toolbar._views.clear()
        toolbar._positions.clear()
        toolbar._update_view()

        if self.listWidget_numerator.currentRow() is not -1:
            self.last_num = self.listWidget_numerator.currentRow()
            self.last_num_text = self.listWidget_numerator.currentItem().text()
        if self.listWidget_denominator.currentRow() is not -1:
            self.last_den = self.listWidget_denominator.currentRow()
            self.last_den_text = self.listWidget_denominator.currentItem().text()

        for data in list_data_set:
            df = data['processing_ret']['data']
            df = df.sort_values('energy')
            result = df[self.last_num_text] / df[self.last_den_text]
            ylabel = '{} / {}'.format(self.last_num_text, self.last_den_text)

            self.bin_offset = 0
            if self.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                warnings.filterwarnings('error')
                try:
                    result_log = np.log(result)
                except Warning as wrn:
                    self.bin_offset = 0.1 + np.abs(result.min())
                    print(
                        '{}: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(
                            wrn, self.bin_offset))
                    result_log = np.log(result + self.bin_offset)
                    # self.checkBox_log.setChecked(False)
                warnings.filterwarnings('default')
                result = result_log

            if self.checkBox_neg.checkState() > 0:
                result = -result

            figure.ax.plot(df['energy'].iloc[:len(result)], result)
            figure.ax.set_ylabel(ylabel)
            figure.ax.set_xlabel('energy')
            figure.tight_layout()

        figure.ax.legend(handles=handles)
        figure.tight_layout()

        figure.canvas.draw_idle()

    def plot_data(self, data):
        df = data['processing_ret']['data']
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

        self.figure_old_scans_3.ax.plot(df['energy'], division)

        last_trace = self.figure_old_scans_3.ax.get_lines()[len(self.figure_old_scans_3.ax.get_lines()) - 1]
        patch = mpatches.Patch(color=last_trace.get_color(), label=data['processing_ret']['metadata']['name'])
        self.handles_bin.append(patch)

        self.figure_old_scans_3.ax.legend(handles=self.handles_bin)
        self.figure_old_scans_3.tight_layout()
        self.canvas_old_scans_3.draw_idle()

        #self.update_k_view(df)

    def plot_interp_data(self, data):
        df = data['processing_ret']['data']
        #df = pd.DataFrame.from_dict(json.loads(data['processing_ret']['data']))
        df = df.sort_values('energy')
        self.df = df
        self.interp_data_sets.append(data)
        self.create_lists(df.keys(), df.keys())
        self.update_listWidgets()
        self.push_replot_file.setEnabled(True)

        division = df[self.last_num_text] / df[self.last_den_text]

        if self.checkBox_log.checkState() > 0:
            division[division < 0] = 1
            division = np.log(division)

        if self.checkBox_neg.checkState() > 0:
            division = -division

        self.figure_old_scans_2.ax.plot(df['energy'], division)

        last_trace = self.figure_old_scans_2.ax.get_lines()[len(self.figure_old_scans_2.ax.get_lines()) - 1]
        patch = mpatches.Patch(color=last_trace.get_color(), label=data['processing_ret']['metadata']['name'])
        self.handles_interp.append(patch)

        self.figure_old_scans_2.ax.legend(handles=self.handles_interp)
        self.figure_old_scans_2.tight_layout()
        self.canvas_old_scans_2.draw_idle()

    def erase_plots(self):
        #self.figure_old_scans.ax.clear()
        #self.toolbar_old_scans._views.clear()
        #self.toolbar_old_scans._positions.clear()
        #self.toolbar_old_scans._update_view()
        #self.canvas_old_scans.draw_idle()

        self.figure_old_scans_2.ax.clear()
        self.figure_old_scans_2.ax2.clear()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        self.toolbar_old_scans_2._update_view()
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3.ax.clear()
        self.figure_old_scans_3.ax2.clear()
        self.toolbar_old_scans_3._views.clear()
        self.toolbar_old_scans_3._positions.clear()
        self.toolbar_old_scans_3._update_view()
        self.canvas_old_scans_3.draw_idle()

    def reset_data_plots(self):
        self.push_replot_file.setEnabled(False)
        self.listWidget_numerator.clear()
        self.listWidget_denominator.clear()
        self.bin_data_sets = []
        self.interp_data_sets = []
        self.handles_interp = []
        self.handles_bin = []
        self.df = pd.DataFrame([])
        self.erase_plots()

    def questionMessage(self, title, question):
        reply = QtWidgets.QMessageBox.question(self, title,
                                               question,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            return True
        elif reply == QtWidgets.QMessageBox.No:
            return False
        else:
            return False
