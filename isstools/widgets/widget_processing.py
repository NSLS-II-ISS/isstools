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

from isstools.xasdata import xasdata
from isstools.conversions import xray

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_processing.ui')

class UIProcessing(*uic.loadUiType(ui_path)):
    def __init__(self,
                 hhm,
                 db,
                 det_dict,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.hhm = hhm
        self.db = db
        self.det_dict = det_dict
        self.gen_parser = xasdata.XASdataGeneric(self.hhm.pulses_per_deg, self.db)

        self.settings = QSettings('ISS Beamline', 'XLive')
        self.edit_E0_2.setText(self.settings.value('e0_processing', defaultValue='11470', type=str))
        self.edit_E0_2.textChanged.connect(self.save_e0_processing_value)
        self.user_dir = self.settings.value('user_dir', defaultValue = '/GPFS/xf08id/User Data/', type = str)

        # Initialize 'processing' tab
        self.push_select_file.clicked.connect(self.selectFile)
        self.push_bin.clicked.connect(self.process_bin)
        self.push_save_bin.clicked.connect(self.save_bin)
        self.push_calibrate.clicked.connect(self.calibrate_offset)
        self.push_replot_exafs.clicked.connect(self.update_k_view)
        self.push_replot_file.clicked.connect(self.replot_bin_equal)
        self.cid = self.canvas_old_scans_2.mpl_connect('button_press_event', self.getX)
        self.edge_found = -1
        # Disable buttons
        self.push_bin.setDisabled(True)
        self.push_save_bin.setDisabled(True)
        self.push_replot_exafs.setDisabled(True)
        self.push_replot_file.setDisabled(True)
        self.active_threads = 0
        self.total_threads = 0
        self.progressBar_processing.setValue(int(np.round(0)))
        self.plotting_list = []
        self.last_num = ''
        self.last_den = ''
        self.last_num_text = 'i0'
        self.last_den_text = 'it'

    def addCanvas(self):
        self.figure_old_scans = Figure()
        self.figure_old_scans.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans = FigureCanvas(self.figure_old_scans)
        self.figure_old_scans.ax = self.figure_old_scans.add_subplot(111)
        self.toolbar_old_scans = NavigationToolbar(self.canvas_old_scans, self, coordinates=True)
        self.plot_old_scans.addWidget(self.toolbar_old_scans)
        self.plot_old_scans.addWidget(self.canvas_old_scans)
        self.canvas_old_scans.draw_idle()

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
            self.selected_filename_bin = [QtWidgets.QFileDialog.getOpenFileName(directory = self.user_dir, filter = '*.txt', parent = self)[0]]
        if len(self.selected_filename_bin[0]):
            if len(self.selected_filename_bin) > 1:
                filenames = []
                self.user_dir = self.selected_filename_bin[0].rsplit('/', 1)[0]
                for name in self.selected_filename_bin:
                    filenames.append(name.rsplit('/', 1)[1])
                filenames = ', '.join(filenames)
            elif len(self.selected_filename_bin) == 1:
                filenames = self.selected_filename_bin[0]
                self.user_dir = filenames.rsplit('/', 1)[0]

            self.settings.setValue('user_dir', self.user_dir)
            self.label_24.setText(filenames)
            self.process_bin_equal()

    def update_listWidgets(self):  # , value_num, value_den):
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

    def process_bin(self):
        self.old_scans_control = 1
        self.old_scans_2_control = 1
        self.old_scans_3_control = 1
        print('[Launching Threads]')
        process_thread = process_bin_thread(self)
        self.canvas_old_scans_2.mpl_disconnect(self.cid)
        if self.edge_found != int(self.edit_E0_2.text()):
            self.edge_found = -1
        process_thread.finished.connect(self.reset_processing_tab)
        self.active_threads += 1
        self.total_threads += 1
        self.progressBar_processing.setValue(
            int(np.round(100 * (self.total_threads - self.active_threads) / self.total_threads)))
        process_thread.start()

    def process_bin_equal(self):
        index = 1
        self.old_scans_control = 1
        self.old_scans_2_control = 1
        self.old_scans_3_control = 1

        self.figure_old_scans.ax.clear()
        self.toolbar_old_scans._views.clear()
        self.toolbar_old_scans._positions.clear()
        self.toolbar_old_scans._update_view()
        self.canvas_old_scans.draw_idle()

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

        print('[Launching Threads]')
        if self.listWidget_numerator.currentRow() is not -1:
            self.last_num = self.listWidget_numerator.currentRow()
            self.last_num_text = self.listWidget_numerator.currentItem().text()
        if self.listWidget_denominator.currentRow() is not -1:
            self.last_den = self.listWidget_denominator.currentRow()
            self.last_den_text = self.listWidget_denominator.currentItem().text()
        self.listWidget_numerator.setCurrentRow(-1)
        self.listWidget_denominator.setCurrentRow(-1)
        t_manager = process_threads_manager(self)
        t_manager.start()

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

    def update_k_view(self):
        e0 = int(self.edit_E0_2.text())
        edge_start = int(self.edit_edge_start.text())
        edge_end = int(self.edit_edge_end.text())
        preedge_spacing = float(self.edit_preedge_spacing.text())
        xanes_spacing = float(self.edit_xanes_spacing.text())
        exafs_spacing = float(self.edit_exafs_spacing.text())
        k_power = float(self.edit_y_power.text())

        energy_string = self.gen_parser.get_energy_string()

        result_orig = self.gen_parser.data_manager.data_arrays[self.listWidget_numerator.currentItem().text()] / \
                      self.gen_parser.data_manager.data_arrays[self.listWidget_denominator.currentItem().text()]

        if self.checkBox_log.checkState() > 0:
            result_orig = np.log(result_orig)

        k_data = self.gen_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         result,
                                                         self.gen_parser.interp_arrays,
                                                         self.gen_parser.data_manager.data_arrays[energy_string],
                                                         result_orig,
                                                         k_power)
        self.figure_old_scans.ax.clear()
        self.toolbar_old_scans._views.clear()
        self.toolbar_old_scans._positions.clear()
        self.toolbar_old_scans._update_view()
        self.figure_old_scans.ax.plot(k_data[0], k_data[1])
        self.figure_old_scans.ax.set_xlabel('k')
        self.figure_old_scans.ax.set_ylabel(r'$\kappa$ * k ^ {}'.format(k_power))  # 'ϰ * k ^ {}'.format(k_power))
        self.figure_old_scans.ax.grid(True)
        self.canvas_old_scans.draw_idle()

    def replot_bin_equal(self):
        # Erase final plot (in case there is old data there)
        self.figure_old_scans_3.ax.clear()
        self.canvas_old_scans_3.draw_idle()

        self.figure_old_scans.ax.clear()
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_3.ax.clear()
        self.figure_old_scans_3.ax2.clear()
        self.canvas_old_scans_3.draw_idle()
        self.toolbar_old_scans_3._views.clear()
        self.toolbar_old_scans_3._positions.clear()
        self.toolbar_old_scans_3._update_view()

        energy_string = self.gen_parser.get_energy_string()

        self.last_num = self.listWidget_numerator.currentRow()
        self.last_num_text = self.listWidget_numerator.currentItem().text()
        self.last_den = self.listWidget_denominator.currentRow()
        self.last_den_text = self.listWidget_denominator.currentItem().text()

        self.den_offset = 0

        array = self.gen_parser.interp_arrays[self.last_den_text][:, 1]
        if self.last_den_text != '1':
            det = [det for det in [self.det_dict[det]['obj'] for det in self.det_dict if hasattr(self.det_dict[det]['obj'], 'dev_name')] if
                   det.dev_name.value == self.last_den_text][0]
            polarity = det.polarity
            if polarity == 'neg':
                if sum(array > 0):
                    array[array > 0] = -array[array > 0]
                    print('invalid value encountered in denominator! Fixed for visualization')
            else:
                if sum(array < 0):
                    array[array < 0] = -array[array < 0]
                    print('invalid value encountered in denominator! Fixed for visualization')

        result = self.gen_parser.interp_arrays[self.last_num_text][:, 1] / (
        self.gen_parser.interp_arrays[self.last_den_text][:, 1] - self.den_offset)
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

        self.figure_old_scans_3.ax.plot(self.gen_parser.interp_arrays[energy_string][:, 1][:len(result)], result, 'b')
        self.figure_old_scans_3.ax.set_ylabel(ylabel)
        self.figure_old_scans_3.ax.set_xlabel(energy_string)
        self.figure_old_scans_3.tight_layout()

        self.figure_old_scans_2.ax.clear()
        self.figure_old_scans_2.ax2.clear()
        self.canvas_old_scans_2.draw_idle()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        self.toolbar_old_scans_2._update_view()

        bin_eq = self.gen_parser.data_manager.binned_eq_arrays

        result = bin_eq[self.listWidget_numerator.currentItem().text()] / bin_eq[
            self.listWidget_denominator.currentItem().text()]
        ylabel = '{} / {}'.format(self.listWidget_numerator.currentItem().text(),
                                  self.listWidget_denominator.currentItem().text())

        if self.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
        ylabel = 'Binned Equally {}'.format(ylabel)

        if self.checkBox_neg.checkState() > 0:
            result = -result

        self.figure_old_scans_2.ax.plot(bin_eq[energy_string], result, 'b')
        self.figure_old_scans_2.ax.set_ylabel(ylabel)
        self.figure_old_scans_2.ax.set_xlabel(energy_string)
        self.figure_old_scans_2.tight_layout()

        if self.checkBox_find_edge.checkState() > 0:
            self.edge_index = self.gen_parser.data_manager.get_edge_index(result)
            if self.edge_index > 0:
                x_edge = self.gen_parser.data_manager.en_grid_eq[self.edge_index]
                y_edge = result[self.edge_index]

                self.figure_old_scans_2.ax.plot(x_edge, y_edge, 'ys')
                edge_path = mpatches.Patch(facecolor='y', edgecolor='black', label='Edge')
                self.figure_old_scans_2.ax.legend(handles=[edge_path])
                self.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(x_edge, y_edge), xy=(x_edge, y_edge),
                                                    textcoords='data')
                print('Edge: ' + str(int(np.round(self.gen_parser.data_manager.en_grid_eq[self.edge_index]))))
                self.edit_E0_2.setText(str(int(np.round(self.gen_parser.data_manager.en_grid_eq[self.edge_index]))))
        else:
            self.edge_index = -1

        result_der = self.gen_parser.data_manager.get_derivative(result)
        self.figure_old_scans_2.ax2.plot(bin_eq[energy_string], result_der, 'r')
        self.figure_old_scans_2.ax2.set_ylabel('Derivative')
        self.figure_old_scans_2.ax2.set_xlabel(energy_string)

        self.canvas_old_scans_3.draw_idle()
        self.canvas_old_scans_2.draw_idle()

        self.push_replot_exafs.setDisabled(True)
        self.push_save_bin.setDisabled(True)

    def reset_processing_tab(self):
        self.active_threads -= 1
        print('[Threads] Number of active threads: {}'.format(self.active_threads))
        self.progressBar_processing.setValue(
            int(np.round(100 * (self.total_threads - self.active_threads) / self.total_threads)))

        while len(self.plotting_list) > 0:
            plot_info = self.plotting_list.pop()
            plot_info[5].plot(plot_info[0], plot_info[1], plot_info[2])
            plot_info[5].set_xlabel(plot_info[3])
            plot_info[5].set_ylabel(plot_info[4])
            plot_info[5].figure.tight_layout()
            if (plot_info[2] == 'ys'):
                edge_path = mpatches.Patch(facecolor='y', edgecolor='black', label='Edge')
                self.figure_old_scans_2.ax.legend(handles=[edge_path])
                self.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(plot_info[0], plot_info[1]),
                                                    xy=(plot_info[0], plot_info[1]), textcoords='data')
            plot_info[6].draw_idle()
        if self.edge_found != -1:
            self.edit_E0_2.setText(str(self.edge_found))

        if self.active_threads == 0:
            print('[ #### All Threads Done #### ]')
            self.total_threads = 0
            # self.progressBar_processing.setValue(int(np.round(100)))
            self.cid = self.canvas_old_scans_2.mpl_connect('button_press_event', self.getX)
            if len(self.selected_filename_bin) > 1:
                self.push_bin.setDisabled(True)
                self.push_replot_exafs.setDisabled(True)
                self.push_save_bin.setDisabled(True)
                self.push_replot_file.setDisabled(True)
            elif len(self.selected_filename_bin) == 1:
                self.push_bin.setEnabled(True)
                if len(self.figure_old_scans.ax.lines):
                    self.push_save_bin.setEnabled(True)
                    self.push_replot_exafs.setEnabled(True)
                else:
                    self.push_save_bin.setEnabled(False)
                    self.push_replot_exafs.setEnabled(False)
                self.push_replot_file.setEnabled(True)
            for line in self.figure_old_scans_3.ax.lines:
                if (line.get_color()[0] == 1 and line.get_color()[2] == 0) or (line.get_color() == 'r'):
                    line.set_zorder(3)
            self.canvas_old_scans_3.draw_idle()

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

# Bin threads:

class process_bin_thread(QThread):
    def __init__(self, gui, index=1, parent_thread=None, parser=None):
        QThread.__init__(self)
        self.gui = gui
        self.parent_thread = parent_thread
        self.index = index
        if parser is None:
            self.gen_parser = self.gui.gen_parser
        else:
            self.gen_parser = parser

    def __del__(self):
        self.wait()

    def run(self):
        print("[Binning Thread {}] Checking Parent Thread".format(self.index))
        if self.parent_thread is not None:
            print("[Binning Thread {}] Parent Thread exists. Waiting...".format(self.index))
            while (self.parent_thread.isFinished() == False):
                QtCore.QCoreApplication.processEvents()
                pass

        # Plot equal spacing bin
        e0 = int(self.gui.edit_E0_2.text())
        edge_start = int(self.gui.edit_edge_start.text())
        edge_end = int(self.gui.edit_edge_end.text())
        preedge_spacing = float(self.gui.edit_preedge_spacing.text())
        xanes_spacing = float(self.gui.edit_xanes_spacing.text())
        exafs_spacing = float(self.gui.edit_exafs_spacing.text())
        k_power = float(self.gui.edit_y_power.text())

        binned = self.gen_parser.bin(e0,
                                     e0 + edge_start,
                                     e0 + edge_end,
                                     preedge_spacing,
                                     xanes_spacing,
                                     exafs_spacing)

        warnings.filterwarnings('error')
        try:
            # print(self.gui.bin_offset)
            result = (binned[self.gui.last_num_text] / (
            binned[self.gui.last_den_text] - self.gui.den_offset)) + self.gui.bin_offset
        except Warning as wrn:
            print('{}: This is not supposed to happen. If it is plotting properly, ignore this message.'.format(wrn))
            # self.gui.checkBox_log.setChecked(False)
        warnings.filterwarnings('default')

        result = binned[self.gui.last_num_text] / binned[self.gui.last_den_text]
        result_orig = (self.gen_parser.data_manager.data_arrays[self.gui.last_num_text] / self.gen_parser.data_manager.data_arrays[self.gui.last_den_text]) + self.gui.bin_offset
        ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

        if self.gui.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
            result_orig = np.log(result_orig)
        ylabel = 'Binned {}'.format(ylabel)

        if self.gui.checkBox_neg.checkState() > 0:
            result = -result
            result_orig = -result_orig

        energy_string = self.gen_parser.get_energy_string()

        plot_info = [binned[energy_string][:len(result)],
                     result,
                     'r',
                     energy_string,
                     ylabel,
                     self.gui.figure_old_scans_3.ax,
                     self.gui.canvas_old_scans_3]
        self.gui.plotting_list.append(plot_info)

        if self.gui.checkBox_der.checkState() > 0:
            result_der = self.gen_parser.data_manager.get_derivative(result)
            plot_info = [binned[energy_string][:len(result_der)],
                         result_der,
                         'g',
                         energy_string,
                         ylabel,
                         self.gui.figure_old_scans_3.ax2,
                         self.gui.canvas_old_scans_3]
            self.gui.plotting_list.append(plot_info)

        k_data = self.gen_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         result,
                                                         self.gen_parser.interp_arrays,
                                                         self.gen_parser.data_manager.data_arrays[energy_string],
                                                         result_orig,
                                                         k_power,
                                                         energy_string)

        plot_info = [k_data[0][:len(k_data[1])], k_data[1], '', 'k', r'$\kappa$ * k ^ {}'.format(k_power),
                     self.gui.figure_old_scans.ax, self.gui.canvas_old_scans]
        self.gui.plotting_list.append(plot_info)

        self.gui.push_replot_exafs.setEnabled(True)
        self.gui.push_save_bin.setEnabled(True)

        if self.gui.checkBox_process_bin.checkState() > 0:
            filename = self.gen_parser.curr_filename_save
            self.gen_parser.data_manager.export_dat(filename)
            print('[Binning Thread {}] File Saved! [{}]'.format(self.index, filename[:-3] + 'dat'))

        print('[Binning Thread {}] Done'.format(self.index))


class process_bin_thread_equal(QThread):
    update_listWidgets = QtCore.pyqtSignal()  # list, list)
    create_lists = QtCore.pyqtSignal(list, list)

    def __init__(self, gui, filename, index=1):
        QThread.__init__(self)
        self.gui = gui
        self.index = index
        print(filename)
        self.filename = filename
        self.gen_parser = xasdata.XASdataGeneric(gui.hhm.pulses_per_deg, gui.db)
        self.gen_parser.curr_filename_save = filename

    def __del__(self):
        self.wait()

    def run(self):
        print('[Binning Equal Thread {}] Starting...'.format(self.index))
        self.gen_parser.loadInterpFile(self.filename)

        ordered_dict = collections.OrderedDict(sorted(self.gen_parser.interp_arrays.items()))
        self.create_lists.emit(list(ordered_dict.keys()), list(ordered_dict.keys()))
        # while(self.gui.listWidget_denominator.count() == 0 or self.gui.listWidget_numerator.count() == 0):
        # print('stuck here')
        # self.gui.app.processEvents()
        # QtCore.QCoreApplication.processEvents()
        # QtWidgets.QApplication.instance().processEvents()
        # ttime.sleep(0.1)
        # self.gui.app.processEvents()

        if not (self.gui.last_num_text in ordered_dict.keys() and self.gui.last_den_text in ordered_dict.keys()):
            self.gui.last_num_text = list(ordered_dict.keys())[2]
            self.gui.last_den_text = list(ordered_dict.keys())[3]

        # if self.gui.listWidget_numerator.count() > 0 and self.gui.listWidget_denominator.count() > 0:
        if (self.gui.last_num_text in ordered_dict.keys() and self.gui.last_den_text in ordered_dict.keys()):
            value_num = ''
            if self.gui.last_num != '' and self.gui.last_num <= len(self.gen_parser.interp_arrays.keys()) - 1:
                items_num = self.gui.last_num
                value_num = [items_num]
            if value_num == '':
                value_num = [2]

            value_den = ''
            if self.gui.last_den != '' and self.gui.last_den <= len(self.gen_parser.interp_arrays.keys()) - 1:
                items_den = self.gui.last_den
                value_den = [items_den]
            if value_den == '':
                if len(self.gen_parser.interp_arrays.keys()) >= 2:
                    value_den = [len(self.gen_parser.interp_arrays.keys()) - 2]
                else:
                    value_den = [0]

            self.update_listWidgets.emit()
            ttime.sleep(0.2)

            energy_string = self.gen_parser.get_energy_string()

            self.gui.den_offset = 0
            self.gui.bin_offset = 0

            array = self.gui.gen_parser.interp_arrays[self.gui.last_den_text][:, 1]
            if self.gui.last_den_text != '1':
                det = [det for det in [self.gui.det_dict[det]['obj'] for det in self.gui.det_dict if hasattr(self.gui.det_dict[det]['obj'], 'dev_name')] if det.dev_name.value == self.gui.last_den_text][0]
                polarity = det.polarity
                if polarity == 'neg':
                    if sum(array > 0):
                        array[array > 0] = -array[array > 0]
                        print('invalid value encountered in denominator! Fixed for visualization')
                else:
                    if sum(array < 0):
                        array[array < 0] = -array[array < 0]
                        print('invalid value encountered in denominator! Fixed for visualization')

            result = self.gen_parser.interp_arrays[self.gui.last_num_text][:, 1] / (
            self.gen_parser.interp_arrays[self.gui.last_den_text][:, 1] - self.gui.den_offset)
            ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

            if self.gui.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                warnings.filterwarnings('error')
                try:
                    result_log = np.log(result)
                except Warning as wrn:
                    self.gui.bin_offset = 0.1 + np.abs(result.min())
                    print(
                        '{}: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(
                            wrn, self.gui.bin_offset))
                    result_log = np.log(result + self.gui.bin_offset)
                    # self.gui.checkBox_log.setChecked(False)
                warnings.filterwarnings('default')
                result = result_log

            if self.gui.checkBox_neg.checkState() > 0:
                result = -result

            plot_info = [self.gen_parser.interp_arrays[energy_string][:, 1][:len(result)],
                         result,
                         'b',
                         energy_string,
                         ylabel,
                         self.gui.figure_old_scans_3.ax,
                         self.gui.canvas_old_scans_3]
            self.gui.plotting_list.append(plot_info)

            bin_eq = self.gen_parser.bin_equal(en_spacing=0.5)

            result = bin_eq[self.gui.last_num_text] / bin_eq[self.gui.last_den_text]
            ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

            if self.gui.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                result = np.log(result)
            ylabel = 'Binned Equally {}'.format(ylabel)

            if self.gui.checkBox_neg.checkState() > 0:
                result = -result

            plot_info = [bin_eq[energy_string][:len(result)],
                         result,
                         'b',
                         energy_string,
                         ylabel,
                         self.gui.figure_old_scans_2.ax,
                         self.gui.canvas_old_scans_2]
            self.gui.plotting_list.append(plot_info)

            if self.gui.checkBox_find_edge.checkState() > 0:

                self.gui.edge_index = self.gen_parser.data_manager.get_edge_index(result)
                self.gui.edge_found = -1
                if self.gui.edge_index > 0:
                    x_edge = self.gen_parser.data_manager.en_grid_eq[self.gui.edge_index]
                    y_edge = result[self.gui.edge_index]

                    self.gui.figure_old_scans_2.ax.plot(x_edge, y_edge, 'ys')
                    plot_info = [x_edge,
                                 y_edge,
                                 'ys',
                                 '',
                                 '',
                                 self.gui.figure_old_scans_2.ax,
                                 self.gui.canvas_old_scans_2]
                    self.gui.plotting_list.append(plot_info)

                    print('[Binning Equal Thread {}] Edge: '.format(self.index) + str(
                        int(np.round(self.gen_parser.data_manager.en_grid_eq[self.gui.edge_index]))))
                    self.gui.edge_found = str(
                        int(np.round(self.gen_parser.data_manager.en_grid_eq[self.gui.edge_index])))
            else:
                self.gui.edge_index = -1

            result_der = self.gen_parser.data_manager.get_derivative(result)

            if self.gui.checkBox_neg.checkState() > 0:
                result_der = -result_der

            plot_info = [bin_eq[energy_string][:len(result_der)],
                         result_der,
                         'r', energy_string,
                         'Derivative',
                         self.gui.figure_old_scans_2.ax2,
                         self.gui.canvas_old_scans_2]
            self.gui.plotting_list.append(plot_info)

        print('[Binning Equal Thread {}] Done'.format(self.index))


class process_threads_manager(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui

    def __del__(self):
        self.wait()

    def run(self):
        index = 1
        self.gui.canvas_old_scans_2.mpl_disconnect(self.gui.cid)
        for filename in self.gui.selected_filename_bin:
            print(filename)
            process_thread_equal = process_bin_thread_equal(self.gui, filename, index)
            # self.gui.connect(process_thread_equal, pyqtSignal("finished()"), self.gui.reset_processing_tab)
            process_thread_equal.update_listWidgets.connect(self.gui.update_listWidgets)
            process_thread_equal.create_lists.connect(self.gui.create_lists)
            process_thread_equal.finished.connect(self.gui.reset_processing_tab)
            process_thread_equal.start()
            self.gui.active_threads += 1
            self.gui.total_threads += 1
            self.gui.edge_found = -1

            self.gui.curr_filename_save = filename
            if self.gui.checkBox_process_bin.checkState() > 0:
                process_thread = process_bin_thread(self.gui, index, process_thread_equal,
                                                    process_thread_equal.gen_parser)
                # self.gui.connect(process_thread, pyqtSignal("finished()"), self.gui.reset_processing_tab)
                process_thread.finished.connect(self.gui.reset_processing_tab)
                process_thread.start()
                self.gui.active_threads += 1
                self.gui.total_threads += 1
            index += 1
        self.gui.gen_parser = process_thread_equal.gen_parser
