import numpy as np
import PyQt4
from PyQt4 import uic, QtGui, QtCore, Qt
from PyQt4.QtCore import QThread, SIGNAL, QSettings
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.widgets import Cursor
import matplotlib.patches as mpatches
from scipy.optimize import curve_fit

import pkg_resources
import time as ttime
import math
import bluesky.plans as bp
from subprocess import call

from isstools.trajectory.trajectory  import trajectory
from isstools.trajectory.trajectory import trajectory_manager
from isstools.xasdata import xasdata
from isstools.xiaparser import xiaparser
from isstools.elements import elements
from isstools.dialogs import UpdateUserDialog
from isstools.dialogs import UpdatePiezoDialog
from isstools.dialogs import UpdateAngleOffset
from isstools.conversions import xray
import os
from os import listdir
from os.path import isfile, join
import inspect
import re
import sys
import collections
import signal

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

# def my_plan(dets, some, other, param):
#	...


def auto_redraw_factory(fnc):

    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback

class ScanGui(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()
    es_shutter_sig = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs, tune_funcs, prep_traj_plan, RE, db, hhm, detectors, es_shutter, det_dict, motors_list, general_scan_func, parent=None, *args, **kwargs):

        if 'write_html_log' in kwargs:
            self.html_log_func = kwargs['write_html_log']
            del kwargs['write_html_log']
        else:
            self.html_log_func = None

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.fig = fig = self.figure_content()
        self.addCanvas()
        self.run_start.clicked.connect(self.run_scan)
        self.run_check_gains.clicked.connect(self.run_gains_test)
        self.prep_traj_plan = prep_traj_plan
        self.RE = RE
        self.RE.last_state = ''
        self.db = db
        self.hhm = hhm
        self.hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar) 
        self.progressBar.setValue(0)
        self.abs_parser = xasdata.XASdataAbs() 
        self.flu_parser = xasdata.XASdataFlu() 
        self.gen_parser = xasdata.XASdataGeneric(self.db)
        self.push_update_user.clicked.connect(self.update_user)
        self.label_angle_offset.setText('{0:.4f}'.format(float(RE.md['angle_offset'])))
        self.es_shutter = es_shutter
        self.det_dict = det_dict
        self.motors_list = motors_list
        self.gen_scan_func = general_scan_func

        # Write metadata in the GUI
        self.label_6.setText('{}'.format(RE.md['year']))
        self.label_7.setText('{}'.format(RE.md['cycle']))
        self.label_8.setText('{}'.format(RE.md['PROPOSAL']))
        self.label_9.setText('{}'.format(RE.md['SAF']))
        self.label_10.setText('{}'.format(RE.md['PI']))

        # Initialize 'trajectory' tab
        self.traj = trajectory()
        self.traj_manager = trajectory_manager(hhm)
        self.trajectory_path = '/GPFS/xf08id/trajectory/'
        #self.get_traj_names()
        self.comboBox_2.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.comboBox_3.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.comboBox_3.setCurrentIndex(self.traj_manager.current_lut() - 1)
        self.push_build_trajectory.clicked.connect(self.build_trajectory)
        self.push_save_trajectory.clicked.connect(self.save_trajectory)
        self.push_update_offset.clicked.connect(self.update_offset)
        self.push_select_traj_file.clicked.connect(self.get_traj_names)
        self.push_load_trajectory.clicked.connect(self.load_trajectory)
        self.push_init_trajectory.clicked.connect(self.init_trajectory)
        self.push_read_traj_info.clicked.connect(self.read_trajectory_info)
        self.push_prepare_trajectory.clicked.connect(self.run_prep_traj)
        self.push_plot_traj.clicked.connect(self.plot_traj_file)
        self.push_plot_traj.setDisabled(True)
        self.push_save_trajectory.setDisabled(True)

        # Initialize XIA tab
        self.xia_parser = xiaparser.xiaparser()
        self.push_gain_matching.clicked.connect(self.run_gain_matching)

        # Initialize detectors
        self.xia = detectors['xia']
        self.pba1 = detectors['pba1']
        self.pba2 = detectors['pba2']
        self.pb9 = detectors['pb9']

        # Initialize 'tune' tab
        self.push_tune.clicked.connect(self.run_tune)
        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.tune_funcs = tune_funcs
        self.tune_funcs_names = [tune.__name__ for tune in tune_funcs]
        self.comboBox_4.addItems(self.tune_funcs_names)
        self.det_list = [det.dev_name.value if hasattr(det, 'dev_name') else det.name for det in det_dict.keys()] #[det.name for det in det_dict.keys()]
        self.det_sorted_list = self.det_list
        self.det_sorted_list.sort()
        self.mot_list = [motor.name for motor in self.motors_list]
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()
        self.comboBox_gen_det.addItems(self.det_sorted_list)
        self.comboBox_gen_mot.addItems(self.mot_sorted_list)
        self.comboBox_gen_det.currentIndexChanged.connect(self.process_detsig)
        self.process_detsig()
        for i in range(self.comboBox_gen_det.count()):
            if 'bpm_es' == list(self.det_dict.keys())[i].name:
                self.bpm_es = list(self.det_dict.keys())[i]
                break

        # Initialize persistent values
        self.settings = QSettings('ISS Beamline', 'XLive')
        self.edit_E0_2.setText(self.settings.value('e0_processing', defaultValue = '11470', type = str))
        self.edit_E0_2.textChanged.connect(self.save_e0_processing_value)

        self.piezo_line = self.settings.value('piezo_line', defaultValue = 420, type = int)
        self.piezo_center = self.settings.value('piezo_center', defaultValue = 655, type = float)

        # Initialize 'run' tab
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.run_type.addItems(self.plan_funcs_names)
        self.push_re_abort.clicked.connect(self.re_abort)
        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)
        self.checkBox_piezo_fb.stateChanged.connect(self.toggle_piezo_fb)

        self.piezo_thread = piezo_fb_thread(self)
        self.update_piezo.clicked.connect(self.update_piezo_params)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_re_state)
        self.timer.start(1000)

        self.run_type.currentIndexChanged.connect(self.populateParams)
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.populateParams(0)

        times_arr = np.array(list(self.pba1.adc1.averaging_points.enum_strs))
        times_arr[times_arr == ''] = 0.0
        times_arr = list(times_arr.astype(np.float) * self.pba1.adc1.sample_rate.value / 100000)
        times_arr = [str(elem) for elem in times_arr]
        self.comboBox_samp_time.addItems(times_arr)
        self.comboBox_samp_time.setCurrentIndex(self.pba1.adc1.averaging_points.value)

        self.lineEdit_samp_time.setText(str(self.pb9.enc1.filter_dt.value / 100000))

        # Initialize Ophyd elements
        self.shutter_a = elements.shutter('XF:08ID-PPS{Sh:FE}', name = 'shutter_a')
        self.shutter_b = elements.shutter('XF:08IDA-PPS{PSh}', name = 'shutter_b')
        self.shutter_a.state.subscribe(self.update_shutter)
        self.shutter_b.state.subscribe(self.update_shutter)
        self.push_fe_shutter.clicked.connect(self.toggle_fe_button)
        self.push_ph_shutter.clicked.connect(self.toggle_ph_button)
        self.push_es_shutter.clicked.connect(self.toggle_es_button)

        if self.shutter_a.state.value == 0:
            self.push_fe_shutter.setStyleSheet("background-color: lime")
        else:
            self.push_fe_shutter.setStyleSheet("background-color: red")
        if self.shutter_b.state.value == 0:
            self.push_ph_shutter.setStyleSheet("background-color: lime")
        else:
            self.push_ph_shutter.setStyleSheet("background-color: red")
        self.shutters_sig.connect(self.change_shutter_color)

        self.es_shutter_sig.connect(self.change_es_shutter_color)
        self.es_shutter.subscribe(self.update_es_shutter)
        self.change_es_shutter_color()

        # Initialize 'processing' tab
        self.push_select_file.clicked.connect(self.selectFile)
        self.push_bin.clicked.connect(self.process_bin)
        self.push_save_bin.clicked.connect(self.save_bin)
        self.push_calibrate.clicked.connect(self.calibrate_offset)
        self.push_replot_exafs.clicked.connect(self.update_k_view)
        self.push_replot_file.clicked.connect(self.replot_bin_equal)
        self.cid = self.canvas_old_scans_2.mpl_connect('button_press_event', self.getX)
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

        # Redirect terminal output to GUI
        sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
        sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

    def toggle_piezo_fb(self, value):
        if value == 0:
            self.piezo_thread.go = 0
        else:
            self.piezo_thread.start()

    def update_piezo_params(self):
        dlg = UpdatePiezoDialog.UpdatePiezoDialog(str(self.piezo_line), str(self.piezo_center))
        if dlg.exec_():
            piezo_line, piezo_center = dlg.getValues()
            self.piezo_line = int(piezo_line)
            self.piezo_center = float(piezo_center)
            self.settings.setValue('piezo_line', self.piezo_line)
            self.settings.setValue('piezo_center', self.piezo_center)

    def update_user(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.label_6.text(), self.label_7.text(), self.label_8.text(), self.label_9.text(), self.label_10.text())
        if dlg.exec_():
            self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'], self.RE.md['SAF'], self.RE.md['PI'] = dlg.getValues()
            self.label_6.setText('{}'.format(self.RE.md['year']))
            self.label_7.setText('{}'.format(self.RE.md['cycle']))
            self.label_8.setText('{}'.format(self.RE.md['PROPOSAL']))
            self.label_9.setText('{}'.format(self.RE.md['SAF']))
            self.label_10.setText('{}'.format(self.RE.md['PI']))

    def update_offset(self):
        dlg = UpdateAngleOffset.UpdateAngleOffset(self.label_angle_offset.text())
        if dlg.exec_():
            self.RE.md['angle_offset'] = dlg.getValues()
            self.label_angle_offset.setText('{}'.format(self.RE.md['angle_offset']))

    def update_es_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        self.es_shutter_sig.emit()

    def change_es_shutter_color(self):
        if self.es_shutter.state == 'closed':
            self.push_es_shutter.setStyleSheet("background-color: red")
        elif self.es_shutter.state == 'open':
            self.push_es_shutter.setStyleSheet("background-color: lime")

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if(kwargs['obj'] == self.shutter_a.state):
            current_button = self.push_fe_shutter
        elif(kwargs['obj'] == self.shutter_b.state):
            current_button = self.push_ph_shutter

        self.current_button = current_button
        if int(value) == 0:
            self.current_button_color = 'lime'
        if int(value) == 1:
            self.current_button_color = 'red'
        self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)

    def toggle_fe_button(self):
        if(int(self.shutter_a.state.value)):
            self.shutter_a.open()
        else:
            self.shutter_a.close()

    def toggle_ph_button(self):
        if(int(self.shutter_b.state.value)):
            self.shutter_b.open()
        else:
            self.shutter_b.close()

    def toggle_es_button(self):
        if(self.es_shutter.state == 'closed'):
            self.es_shutter.open()
        else:
            self.es_shutter.close()

    def update_progress(self, pvname = None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        self.progressBar.setValue(int(np.round(self.progressValue)))

    def getX(self, event):
        self.edit_E0_2.setText(str(int(np.round(event.xdata))))

    def save_e0_processing_value(self, string):
        self.settings.setValue('e0_processing', string)

    def selectFile(self):
        if self.checkBox_process_bin.checkState() > 0:
            self.selected_filename_bin = QtGui.QFileDialog.getOpenFileNames(directory = '/GPFS/xf08id/User Data/', filter = '*.txt')
        else:
            self.selected_filename_bin = [QtGui.QFileDialog.getOpenFileName(directory = '/GPFS/xf08id/User Data/', filter = '*.txt')]
        if self.selected_filename_bin:
            if len(self.selected_filename_bin) > 1:
                filenames = []
                for name in self.selected_filename_bin:
                    filenames.append(name.rsplit('/', 1)[1])
                filenames = ', '.join(filenames)
            elif len(self.selected_filename_bin) == 1:
                filenames = self.selected_filename_bin[0]

            self.label_24.setText(filenames)
            self.process_bin_equal()

    def save_bin(self):
        filename = self.curr_filename_save
        self.gen_parser.data_manager.export_dat_gen(filename)
        print('[Save File] File Saved! [{}]'.format(filename[:-3] + 'dat'))

    def calibrate_offset(self):
        ret = self.questionMessage('Confirmation', 'Are you sure you would like to calibrate it?')
        if not ret:
            print ('[E0 Calibration] Aborted!')
            return False
        self.RE.md['angle_offset'] = str(float(self.RE.md['angle_offset']) - (xray.energy2encoder(float(self.edit_E0_2.text())) - xray.energy2encoder(float(self.edit_ECal.text())))/360000)
        self.label_angle_offset.setText('{0:.4f}'.format(float(self.RE.md['angle_offset'])))
        print ('[E0 Calibration] New value: {}\n[E0 Calibration] Completed!'.format(self.RE.md['angle_offset']))


    def update_k_view(self):
        e0 = int(self.edit_E0_2.text())
        edge_start = int(self.edit_edge_start.text())
        edge_end = int(self.edit_edge_end.text())
        preedge_spacing = float(self.edit_preedge_spacing.text())
        xanes_spacing = float(self.edit_xanes_spacing.text())
        exafs_spacing = float(self.edit_exafs_spacing.text())
        k_power = float(self.edit_y_power.text())

        energy_string = self.gen_parser.get_energy_string()

        result_orig = self.gen_parser.data_manager.data_arrays[self.listWidget_numerator.currentItem().text()] / self.gen_parser.data_manager.data_arrays[self.listWidget_denominator.currentItem().text()]

        if self.checkBox_log.checkState() > 0:
            result_orig = np.log(result_orig)

        k_data = self.gen_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         result,
                                                         self.gen_parser.data_manager.sorted_matrix[:, 0],
                                                         self.gen_parser.data_manager.data_arrays[energy_string],
                                                         result_orig,
                                                         k_power)
        self.figure_old_scans.ax.cla()
        self.figure_old_scans.ax.plot(k_data[0], k_data[1])
        self.figure_old_scans.ax.set_xlabel('k')
        self.figure_old_scans.ax.set_ylabel(r'$\kappa$ * k ^ {}'.format(k_power)) #'ϰ * k ^ {}'.format(k_power))
        self.figure_old_scans.ax.grid(True)
        self.canvas_old_scans.draw_idle()

    def process_bin(self):
        self.old_scans_control = 1
        self.old_scans_2_control = 1
        self.old_scans_3_control = 1
        print('[Launching Threads]')
        process_thread = process_bin_thread(self) 
        self.canvas_old_scans_2.mpl_disconnect(self.cid)
        self.connect(process_thread, SIGNAL("finished()"), self.reset_processing_tab)
        self.active_threads += 1
        self.total_threads += 1
        self.progressBar_processing.setValue(int(np.round(100 * (self.total_threads - self.active_threads)/self.total_threads)))
        process_thread.start()
        print('[Finished Launching Threads]')

    def replot_bin_equal(self):
        # Erase final plot (in case there is old data there)
        self.figure_old_scans_3.ax.cla()
        self.canvas_old_scans_3.draw_idle()

        self.figure_old_scans.ax.cla()
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_3.ax.cla()
        
        energy_string = self.gen_parser.get_energy_string()

        result = self.gen_parser.interp_arrays[self.listWidget_numerator.currentItem().text()][:, 1] / self.gen_parser.interp_arrays[self.listWidget_denominator.currentItem().text()][:, 1]
        ylabel = '{} / {}'.format(self.listWidget_numerator.currentItem().text(), self.listWidget_denominator.currentItem().text())

        if self.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
        
        self.figure_old_scans_3.ax.plot(self.gen_parser.interp_arrays[energy_string][:, 1], result, 'b')
        self.figure_old_scans_3.ax.set_ylabel(ylabel)
        self.figure_old_scans_3.ax.set_xlabel(energy_string)


        self.figure_old_scans_2.ax.cla()
        self.figure_old_scans_2.ax2.cla()
        self.canvas_old_scans_2.draw_idle()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()


        bin_eq = self.gen_parser.data_manager.binned_eq_arrays

        result = bin_eq[self.listWidget_numerator.currentItem().text()] / bin_eq[self.listWidget_denominator.currentItem().text()]
        ylabel = '{} / {}'.format(self.listWidget_numerator.currentItem().text(), self.listWidget_denominator.currentItem().text())

        if self.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
        ylabel = 'Binned Equally {}'.format(ylabel)
        
        self.figure_old_scans_2.ax.plot(bin_eq[energy_string], result, 'b')
        self.figure_old_scans_2.ax.set_ylabel(ylabel)
        self.figure_old_scans_2.ax.set_xlabel(energy_string)


        self.edge_index = self.gen_parser.data_manager.get_edge_index(result)
        if self.edge_index > 0:
                    
            x_edge = self.gen_parser.data_manager.en_grid[self.edge_index]
            y_edge = result[self.edge_index]

            self.figure_old_scans_2.ax.plot(x_edge, y_edge, 'ys')
            edge_path = mpatches.Patch(facecolor='y', edgecolor = 'black', label='Edge')
            self.figure_old_scans_2.ax.legend(handles = [edge_path])
            self.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(x_edge, y_edge), xy=(x_edge, y_edge), textcoords='data')
            print('Edge: ' + str(int(np.round(self.gen_parser.data_manager.en_grid[self.edge_index]))))
            self.edit_E0_2.setText(str(int(np.round(self.gen_parser.data_manager.en_grid[self.edge_index]))))
        

        result_der = self.gen_parser.data_manager.get_derivative(result)
        self.figure_old_scans_2.ax2.plot(bin_eq[energy_string], result_der, 'r')
        self.figure_old_scans_2.ax2.set_ylabel('Derivative')
        self.figure_old_scans_2.ax2.set_xlabel(energy_string)


        self.canvas_old_scans_3.draw_idle()
        self.canvas_old_scans_2.draw_idle()

        self.push_replot_exafs.setDisabled(True)
        self.push_save_bin.setDisabled(True)
        

    def process_bin_equal(self):
        index = 1
        self.old_scans_control = 1
        self.old_scans_2_control = 1
        self.old_scans_3_control = 1

        self.figure_old_scans.ax.cla()
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_2.ax.cla()
        self.figure_old_scans_2.ax2.cla()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3.ax.cla()
        self.canvas_old_scans_3.draw_idle()

        print('[Launching Threads]')
        if self.listWidget_numerator.currentRow() is not -1:
            self.last_num = self.listWidget_numerator.currentRow()
        if self.listWidget_denominator.currentRow() is not -1:
            self.last_den = self.listWidget_denominator.currentRow()
        self.listWidget_numerator.setCurrentRow(-1)
        self.listWidget_denominator.setCurrentRow(-1)
        t_manager = process_threads_manager(self)
        t_manager.start()
        print('[Finished Launching Threads]')


    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        # Maybe QtextEdit_terminal.append() works as well, but this is how I do it:
        cursor = self.textEdit_terminal.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.textEdit_terminal.setTextCursor(cursor)
        self.textEdit_terminal.ensureCursorVisible()
        #sys.__stdout__.writelines(text)

    def populateParams(self, index):
        for i in range(len(self.params1)):
            self.gridLayout_13.removeWidget(self.params1[i])
            self.gridLayout_13.removeWidget(self.params2[i])
            self.gridLayout_13.removeWidget(self.params3[i])
            self.params1[i].deleteLater()
            self.params2[i].deleteLater()
            self.params3[i].deleteLater()
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.param_types = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default, signature.parameters[list(signature.parameters)[i]].annotation)
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)


    def addParamControl(self, name, default, annotation):
        rows = int((self.gridLayout_13.count())/3)
        param1 = QtGui.QLabel('Par ' + str(rows + 1))

        param2 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtGui.QSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtGui.QDoubleSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtGui.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        elif annotation == str:
            param2 = QtGui.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        if param2 is not None:
            param3 = QtGui.QLabel(default)
            self.gridLayout_13.addWidget(param1, rows, 0, QtCore.Qt.AlignTop)
            self.gridLayout_13.addWidget(param2, rows, 1, QtCore.Qt.AlignTop)
            self.gridLayout_13.addWidget(param3, rows, 2, QtCore.Qt.AlignTop)
            self.params1.append(param1)
            self.params2.append(param2)
            self.params3.append(param3)

    def get_traj_names(self):
        #self.comboBox.clear()
        #self.comboBox.addItems([f for f in sorted(listdir(self.trajectory_path)) if isfile(join(self.trajectory_path, f))])
        self.label_56.setText(QtGui.QFileDialog.getOpenFileName(directory = self.trajectory_path, filter = '*.txt').rsplit('/',1)[1])
        self.push_plot_traj.setEnabled(True)

    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='0.89')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax = self.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw_idle()

        self.figure_single_trajectory = Figure()
        self.figure_single_trajectory.set_facecolor(color='0.89')
        self.canvas_single_trajectory = FigureCanvas(self.figure_single_trajectory)
        self.figure_single_trajectory.ax = self.figure_single_trajectory.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas_single_trajectory, self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plot_single_trajectory.addWidget(self.toolbar)
        self.plot_single_trajectory.addWidget(self.canvas_single_trajectory)
        self.canvas_single_trajectory.draw_idle()

        self.figure_full_trajectory = Figure()
        self.figure_full_trajectory.set_facecolor(color='0.89')
        self.canvas_full_trajectory = FigureCanvas(self.figure_full_trajectory)
        self.figure_full_trajectory.add_subplot(111)
        self.figure_full_trajectory.ax = self.figure_full_trajectory.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas_full_trajectory, self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plot_full_trajectory.addWidget(self.toolbar)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.canvas_full_trajectory.draw_idle()

        self.figure_tune = Figure()
        self.figure_tune.set_facecolor(color='0.89')
        self.canvas_tune = FigureCanvas(self.figure_tune)
        self.figure_tune.ax = self.figure_tune.add_subplot(111)
        self.toolbar_tune = NavigationToolbar(self.canvas_tune, self.tab_2, coordinates=True)
        self.plot_tune.addWidget(self.toolbar_tune)
        self.plot_tune.addWidget(self.canvas_tune)
        self.canvas_tune.draw_idle()
        self.cursor_tune = Cursor(self.figure_tune.ax, useblit=True, color='green', linewidth=0.75 )

        self.figure_gen_scan = Figure()
        self.figure_gen_scan.set_facecolor(color='0.89')
        self.canvas_gen_scan = FigureCanvas(self.figure_gen_scan)
        self.figure_gen_scan.ax = self.figure_gen_scan.add_subplot(111)
        self.toolbar_gen_scan = NavigationToolbar(self.canvas_gen_scan, self.tab_2, coordinates=True)
        self.plot_gen_scan.addWidget(self.toolbar_gen_scan)
        self.plot_gen_scan.addWidget(self.canvas_gen_scan)
        self.canvas_gen_scan.draw_idle()
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75 )

        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='0.89')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.figure_gain_matching.add_subplot(111)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw_idle()

        self.figure_old_scans = Figure()
        self.figure_old_scans.set_facecolor(color='0.89')
        self.canvas_old_scans = FigureCanvas(self.figure_old_scans)
        self.figure_old_scans.ax = self.figure_old_scans.add_subplot(111)
        self.toolbar_old_scans = NavigationToolbar(self.canvas_old_scans, self.tab_2, coordinates=True)
        self.plot_old_scans.addWidget(self.toolbar_old_scans)
        self.plot_old_scans.addWidget(self.canvas_old_scans)
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_2 = Figure()
        self.figure_old_scans_2.set_facecolor(color='0.89')
        self.canvas_old_scans_2 = FigureCanvas(self.figure_old_scans_2)
        self.figure_old_scans_2.ax = self.figure_old_scans_2.add_subplot(111)
        self.figure_old_scans_2.ax2 = self.figure_old_scans_2.ax.twinx()
        self.toolbar_old_scans_2 = NavigationToolbar(self.canvas_old_scans_2, self.tab_2, coordinates=True)
        self.plot_old_scans_2.addWidget(self.toolbar_old_scans_2)
        self.plot_old_scans_2.addWidget(self.canvas_old_scans_2)
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3 = Figure()
        self.figure_old_scans_3.set_facecolor(color='0.89')
        self.canvas_old_scans_3 = FigureCanvas(self.figure_old_scans_3)
        self.figure_old_scans_3.ax = self.figure_old_scans_3.add_subplot(111)
        self.toolbar_old_scans_3 = NavigationToolbar(self.canvas_old_scans_3, self.tab_3, coordinates=True)
        self.plot_old_scans_3.addWidget(self.toolbar_old_scans_3)
        self.plot_old_scans_3.addWidget(self.canvas_old_scans_3)
        self.canvas_old_scans_3.draw_idle()



    @property
    def plot_x(self):
        return self.plot_selection_dropdown.value()

    def figure_content(self):
        fig1 = Figure()
        fig1.set_facecolor(color='0.89')
        fig1.stale_callback = auto_redraw_factory(fig1.stale_callback)
        ax1f1 = fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        self.ax = ax1f1
        return fig1

    def run_tune(self):
        if self.shutter_a.state.value == 1 or self.shutter_b.state.value == 1:
            ret = self.questionMessage('Shutter closed', 'Would you like to run the tuning with the shutter closed?') 
            if not ret:
                print ('Aborted!')
                return False 

        self.figure_tune.ax.cla()
        self.canvas_tune.draw_idle()
        self.tune_funcs[self.comboBox_4.currentIndex()](float(self.edit_tune_range.text()), float(self.edit_tune_step.text()), self.spinBox_tune_retries.value(), ax = self.figure_tune.ax)


    def run_gen_scan(self):
        if self.shutter_a.state.value == 1 or self.shutter_b.state.value == 1:
            ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?') 
            if not ret:
                print ('Aborted!')
                return False 

        curr_det = ''
        curr_mot = ''

        for i in range(self.comboBox_gen_det.count()):
            if hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].dev_name.value:
                    curr_det = list(self.det_dict.keys())[i]
            else:
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].name:
                    curr_det = list(self.det_dict.keys())[i]

        for i in range(self.comboBox_gen_mot.count()):
            if self.comboBox_gen_mot.currentText() == self.mot_list[i]:
                curr_mot = self.motors_list[i]

        if(curr_det == ''):
            print('Detector not found. Aborting...')
            raise

        if(curr_mot == ''):
            print('Motor not found. Aborting...')
            raise

        rel_start = -float(self.edit_gen_range.text()) / 2
        rel_stop = float(self.edit_gen_range.text()) / 2
        num_steps = int(round(float(self.edit_gen_range.text()) / float(self.edit_gen_step.text()))) + 1

        self.figure_gen_scan.ax.cla()
        self.canvas_gen_scan.draw_idle()
        self.gen_scan_func(curr_det, self.comboBox_gen_detsig.currentText(), curr_mot, rel_start, rel_stop, num_steps, ax = self.figure_gen_scan.ax)

    def process_detsig(self):
        self.comboBox_gen_detsig.clear()
        for i in range(self.comboBox_gen_det.count()):
            if hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].dev_name.value:
                    curr_det = list(self.det_dict.keys())[i]
                    detsig = self.det_dict[curr_det]
                    self.comboBox_gen_detsig.addItems(detsig)
            else:
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].name:
                    curr_det = list(self.det_dict.keys())[i]
                    detsig = self.det_dict[curr_det]
                    self.comboBox_gen_detsig.addItems(detsig)

    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())


    def build_trajectory(self):
        E0 = int(self.edit_E0.text())
        preedge_lo = int(self.edit_preedge_lo.text())
        preedge_hi = int(self.edit_preedge_hi.text())
        edge_hi = int(self.edit_edge_hi.text())

        postedge_k = float(self.edit_postedge_hi.text())
        postedge_hi = xray.k2e(postedge_k, E0) - E0 #(1000 * ((postedge_k ** 2) + (16.2009 ** 2) * E0/1000) / (16.2009 ** 2)) - E0

        velocity_preedge = int (self.edit_velocity_preedge.text())
        velocity_edge = int(self.edit_velocity_edge.text())
        velocity_postedge = int(self.edit_velocity_postedge.text())

        preedge_stitch_lo = int(self.edit_preedge_stitch_lo.text())
        preedge_stitch_hi = int(self.edit_preedge_stitch_hi.text())
        edge_stitch_lo =  int(self.edit_edge_stitch_lo.text())
        edge_stitch_hi = int(self.edit_edge_stitch_hi.text())
        postedge_stitch_lo = int(self.edit_postedge_stitch_lo.text())
        postedge_stitch_hi = int(self.edit_postedge_stitch_hi.text())

        padding_preedge = float(self.edit_padding_preedge.text())
        padding_postedge = float(self.edit_padding_postedge.text())

        sine_duration = float(self.edit_sine_total_duration.text())

        dsine_preedge_duration = float(self.edit_ds_pree_duration.text())
        dsine_postedge_duration = float(self.edit_ds_poste_duration.text())

        traj_type = self.tabWidget_2.tabText(self.tabWidget_2.currentIndex())

        #Create and interpolate trajectory
        self.traj.define(edge_energy = E0, offsets = ([preedge_lo,preedge_hi,edge_hi,postedge_hi]),velocities = ([velocity_preedge, velocity_edge, velocity_postedge]),\
                        stitching = ([preedge_stitch_lo, preedge_stitch_hi, edge_stitch_lo, edge_stitch_hi, postedge_stitch_lo, postedge_stitch_hi]),\
                        servocycle = 16000, padding_lo = padding_preedge ,padding_hi=padding_postedge, sine_duration = sine_duration, 
                        dsine_preedge_duration = dsine_preedge_duration, dsine_postedge_duration = dsine_postedge_duration, trajectory_type = traj_type)
        self.traj.interpolate()

        #Plot single trajectory motion
        self.figure_single_trajectory.clf()
        ax = self.figure_single_trajectory.add_subplot(111)
        ax.hold(False)
        ax.plot(self.traj.time, self.traj.energy, 'ro')
        ax.hold(True)
        ax.plot(self.traj.time_grid, self.traj.energy_grid, 'b')
        ax.set_xlabel('Time /s')
        ax.set_ylabel('Energy /eV')
        ax2 = ax.twinx()
        ax2.hold(False)
        ax2.plot(self.traj.time_grid[0:-1], self.traj.energy_grid_der, 'r')
        self.canvas_single_trajectory.draw_idle()

        # Tile trajectory
        self.figure_full_trajectory.clf()
        self.traj.tile(reps=self.spinBox_tiling_repetitions.value())

        # Convert to encoder counts
        self.traj.e2encoder(float(self.label_angle_offset.text()))
        
        # Draw
        ax = self.figure_full_trajectory.add_subplot(111)
        ax.hold(False)
        ax.plot(self.traj.encoder_grid, 'b')
        ax.set_xlabel('Servo event / 1/16000 s')
        ax.set_ylabel('Encoder count')
        self.canvas_full_trajectory.draw_idle()

        self.push_save_trajectory.setEnabled(True)


    def save_trajectory(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, 'Save trajectory...', self.trajectory_path, '*.txt')
        if filename[-4:] != '.txt' and len(filename):
            filename += '.txt'
            if (os.path.isfile(filename)): 
                ret = self.questionMessage('Save trajectory...', '{} already exists. Do you want to replace it?'.format(filename.rsplit('/',1)[1]))
                if not ret:
                    print ('Aborted!')
                    return
        elif not len(filename):
            print('\nInvalid name! Select a valid name...')
            return
        print('Filename = {}'.format(filename))

        if(len(self.traj.energy_grid)):
            np.savetxt(filename, 
	               self.traj.encoder_grid, fmt='%d')
            call(['chmod', '666', filename])
            #self.get_traj_names()
            self.label_56.setText(filename.rsplit('/',1)[1])
            self.push_plot_traj.setEnabled(True)
            print('Trajectory saved! [{}]'.format(filename))
        else:
            print('\nCreate the trajectory first...')

    def plot_traj_file(self):
        self.traj.load_trajectory_file('/GPFS/xf08id/trajectory/' + self.label_56.text())#self.comboBox.currentText())

        self.figure_single_trajectory.clf()
        self.figure_single_trajectory.add_subplot(111)
        self.canvas_single_trajectory.draw_idle()

        ax = self.figure_full_trajectory.add_subplot(111)
        ax.hold(False)
        ax.plot(np.arange(0, len(self.traj.energy_grid_loaded)/16000, 1/16000), self.traj.energy_grid_loaded, 'b')
        ax.set_xlabel('Time /s')
        ax.set_ylabel('Energy /eV')
        ax.set_title(self.label_56.text())#self.comboBox.currentText())
        self.canvas_full_trajectory.draw_idle()
        print('Trajectory Load: Done')

        self.push_save_trajectory.setDisabled(True)

    def load_trajectory(self):
        self.traj_manager.load(orig_file_name = self.label_56.text(), new_file_path = self.comboBox_2.currentText())

    def init_trajectory(self):
        self.run_start.setDisabled(True)
        self.traj_manager.init(int(self.comboBox_3.currentText()))
        self.run_start.setEnabled(True)

    def read_trajectory_info(self):
        self.traj_manager.read_info()

    def run_scan(self):
        if self.run_type.currentText() == 'get_offsets':
            if self.shutter_b.state.read()['shutter_b_state']['value'] != 1:
                self.shutter_b.close()
                while self.shutter_b.state.read()['shutter_b_state']['value'] != 1:
                    QtGui.QApplication.processEvents()
                    ttime.sleep(0.1)

        elif self.shutter_a.state.value == 1 or self.shutter_b.state.value == 1:
            ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')    
            if not ret:
                print ('Aborted!')
                return False 

        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.pba1.adc1.sample_rate.value * 100000))
        self.pba1.adc1.averaging_points.put(str(value))
        self.pba1.adc6.averaging_points.put(str(value))
        self.pba1.adc7.averaging_points.put(str(value))
        self.pba2.adc1.averaging_points.put(str(value))
        self.pba2.adc6.averaging_points.put(str(value))
        self.pba2.adc7.averaging_points.put(str(value))

        self.pb9.enc1.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        self.comment = self.params2[0].text()
        if(self.comment):
            print('\nStarting scan...')

            # Get parameters from the widgets and organize them in a dictionary (run_params)
            run_params = {}
            for i in range(len(self.params1)):
                if (self.param_types[i] == int):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == float):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == bool):
                    run_params[self.params3[i].text().split('=')[0]] = bool(self.params2[i].checkState())
                elif (self.param_types[i] == str):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].text()
            
            # Erase last graph
            self.figure.ax.cla()
            self.canvas.draw_idle()

            # Run the scan using the dict created before
            self.current_uid_list = self.plan_funcs[self.run_type.currentIndex()](**run_params, ax=self.figure.ax)

            if self.plan_funcs[self.run_type.currentIndex()].__name__ == 'get_offsets':
                return

            if type(self.current_uid_list) != list:
                self.current_uid_list = [self.current_uid_list]

            filepaths = []
            for i in range(len(self.current_uid_list)):
                self.current_uid = self.current_uid_list[i]
                if self.current_uid == '':
                    self.current_uid = self.db[-1]['start']['uid']

                self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                        '{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                        self.db[self.current_uid]['start']['cycle'],
                                                        self.db[self.current_uid]['start']['PROPOSAL'],
                                                        self.db[self.current_uid]['start']['comment'])

                filepaths.append(self.current_filepath)
                self.gen_parser.load(self.current_uid)

                key_base = 'i0'
                if 'xia_filename' in self.db[self.current_uid]['start']:
                    key_base = 'xia_trigger'
                self.gen_parser.interpolate(key_base = key_base)

                self.figure.ax.cla()
                self.canvas.draw_idle()

                division = self.gen_parser.interp_arrays['i0'][:, 1] / self.gen_parser.interp_arrays['it'][:, 1]
                division[division < 0] = 1
                self.figure.ax.plot(self.gen_parser.interp_arrays['energy'][:, 1], np.log(division))
                self.figure.ax.set_xlabel('Energy (eV)')
                self.figure.ax.set_xlabel('log(i0 / it)')

                # self.gen_parser should be able to generate the interpolated file
            
                if 'xia_filename' in self.db[self.current_uid]['start']:
                    # Parse xia
                    xia_filename = self.db[self.current_uid]['start']['xia_filename']
                    xia_filepath = 'smb://elistavitski-ni/epics/{}'.format(xia_filename)
                    xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                    smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                    smbclient.copy()
                    xia_parser = self.xia_parser
                    xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                    xia_parsed_filepath = self.current_filepath[0 : self.current_filepath.rfind('/') + 1]
                    xia_parser.export_files(dest_filepath = xia_parsed_filepath, all_in_one = True)

                    length = min(len(xia_parser.exporting_array1), len(self.gen_parser.interp_arrays['energy']))

                    mcas = []
                    if 'xia_rois' in self.db[self.current_uid]['start']:
                        xia_rois = self.db[self.current_uid]['start']['xia_rois']
                        for mca_number in range(1, 5):
                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, xia_rois['xia1_mca{}_roi0_low'.format(mca_number)], xia_rois['xia1_mca{}_roi0_high'.format(mca_number)]))
                        mca_sum = sum(mcas)
                    else:
                        for mca_number in range(1, 5):
                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, 6.7, 6.9))
                        mca_sum = sum(mcas)

                    self.gen_parser.interp_arrays['XIA_SUM'] = np.array([self.gen_parser.interp_arrays['energy'][:, 0], mca_sum]).transpose()

                    self.figure.ax.cla()
                    self.figure.ax.plot(self.gen_parser.interp_arrays['energy'][:, 1], -(self.gen_parser.interp_arrays['XIA_SUM'][:, 1]/self.gen_parser.interp_arrays['i0'][:, 1]))

                if self.html_log_func is not None:
                    self.html_log_func(self.current_uid, self.figure)
                self.canvas.draw_idle()
            
                self.gen_parser.export_trace(self.current_filepath[:-4], '')

                # Check saturation:
                try: 
                    warnings = ()
                    if np.max(np.abs(self.gen_parser.interp_arrays['i0'][:,1])) > 3.9:
                        warnings += ('"i0" seems to be saturated',) #(values > 3.9 V), please change the ion chamber gain',)
                    if np.max(np.abs(self.gen_parser.interp_arrays['it'][:,1])) > 3.9:
                        warnings += ('"it" seems to be saturated',) #(values > 3.9 V), please change the ion chamber gain',)
                    if np.max(np.abs(self.gen_parser.interp_arrays['ir'][:,1])) > 9.9:
                        warnings += ('"ir" seems to be saturated',) #(values > 9.9 V), please change the ion chamber gain',)
                    if len(warnings):
                        raise Warning(warnings)

                except Warning as warnings:
                    warningtxt = ''
                    for warning in warnings.args[0]:
                        print('Warning: {}'.format(warning))
                        warningtxt += '{}\n'.format(warning)
                    warningtxt += 'Check the gains of the ion chambers'
                    QtGui.QMessageBox.warning(self, 'Warning!', warningtxt)
                    #raise

                self.canvas.draw_idle()

            if self.checkBox_auto_process.checkState() > 0 and self.active_threads == 0: # Change to a control
                self.tabWidget.setCurrentIndex(4)
                self.selected_filename_bin = filepaths
                self.label_24.setText(' '.join(filepath[filepath.rfind('/') + 1 : len(filepath)] for filepath in filepaths))
                self.process_bin_equal()

        else:
            print('\nPlease, type a comment about the scan in the field "comment"\nTry again')


    def re_abort(self):
        self.RE.abort()


    def update_re_state(self):
        palette = self.label_11.palette()
        if(self.RE.state == 'idle'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif(self.RE.state == 'running'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif(self.RE.state == 'paused'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_11.setPalette(palette)
        self.label_11.setText(self.RE.state)
        if self.RE.state != self.RE.last_state:
            self.RE.last_state = self.RE.state

    def run_gains_test(self):

        def handler(signum, frame):
            print("Could not open shutters")
            raise Exception("end of time")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(6)

        if self.shutter_b.state.read()['shutter_b_state']['value'] != 0:
            try:
                self.shutter_b.open()
            except Exception as exc: 
                print('Timeout! Aborting!')
                return

            while self.shutter_b.state.read()['shutter_b_state']['value'] != 0:
                QtGui.QApplication.processEvents()
                ttime.sleep(0.1)

        if self.shutter_a.state.read()['shutter_a_state']['value'] != 0:
            try:
                self.shutter_a.open()
            except: 
                print('Timeout! Aborting!')
                return

            while self.shutter_b.state.read()['shutter_a_state']['value'] != 0:
                QtGui.QApplication.processEvents()
                ttime.sleep(0.1)

        signal.alarm(0)

        if self.es_shutter.state == 'closed':
            self.es_shutter.open()

        for func in self.plan_funcs:
            if func.__name__ == 'get_offsets':
                getoffsets_func = func
                break
        self.current_uid_list = getoffsets_func(10, dummy_read=True)

        self.es_shutter.close()

        print('Done!')            

        

    def run_gain_matching(self):
        channels = range(4)
            
        ax = self.figure_gain_matching.add_subplot(111)
        gain_adjust = [0.001, 0.001, 0.001, 0.001]
        diff = [0, 0, 0, 0]
        diff_old = [0, 0, 0, 0]

        # Run number of iterations defined in the text edit edit_gain_matching_iterations:
        for i in range(int(self.edit_gain_matching_iterations.text())):
            self.xia.collect_mode.put('MCA spectra')
            ttime.sleep(0.25)
            self.xia.mode.put('Real time')
            ttime.sleep(0.25)
            self.xia.real_time.put('1')
            self.xia.capt_start_stop.put(1)
            ttime.sleep(0.05)
            self.xia.erase_start.put(1)
            ttime.sleep(2)
            ax.cla()

            # For each channel:
            for j in channels:
                # If checkbox of current channel is checked:
                if getattr(self, "checkBox_gm_ch{}".format(j + 1)).checkState() > 0:
        
                    # Get current channel pre-amp gain:
                    curr_ch_gain = getattr(self.xia, "pre_amp_gain{}".format(j + 1))

                    coeff = self.xia_parser.gain_matching(self.xia, self.edit_center_gain_matching.text(), 
                                              self.edit_range_gain_matching.text(), channels[j] + 1, ax)
                    # coeff[0] = Intensity
                    # coeff[1] = Fitted mean
                    # coeff[2] = Sigma

                    diff[j] = float(self.edit_gain_matching_target.text()) - float(coeff[1]*1000)

                    if i != 0:
                        sign = (diff[j] * diff_old[j]) /  math.fabs(diff[j] * diff_old[j])
                        if int(sign) == -1:
                            gain_adjust[j] /= 2
                    print('Chan ' + str(j + 1) + ': ' + str(diff[j]) + '\n')

                    # Update current channel pre-amp gain:
                    curr_ch_gain.put(curr_ch_gain.value - diff[j] * gain_adjust[j])
                    diff_old[j] = diff[j]

                    self.canvas_gain_matching.draw_idle()

    def update_listWidgets(self, value_num, value_den):
        if(type(value_num[0]) == int):
            if value_num[0] < self.listWidget_numerator.count():
                self.listWidget_numerator.setCurrentRow(value_num[0])
            else:
                self.listWidget_numerator.setCurrentRow(0)
        #else:
        #    self.listWidget_numerator.setCurrentItem(value_num[0])

        if(type(value_den[0]) == int):
            if value_den[0] < self.listWidget_denominator.count():
                self.listWidget_denominator.setCurrentRow(value_den[0])
            else:
                self.listWidget_denominator.setCurrentRow(0)
        #else:
        #    self.listWidget_denominator.setCurrentItem(value_den[0])

        
    def create_lists(self, list_num, list_den):
        self.listWidget_numerator.clear()
        self.listWidget_denominator.clear()
        self.listWidget_numerator.insertItems(0, list_num)
        self.listWidget_denominator.insertItems(0, list_den)
        


    def questionMessage(self, title, question):    
        reply = QtGui.QMessageBox.question(self, title,
                question,
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            return True
        elif reply == QtGui.QMessageBox.No:
            return False
        else:
            return False

    def show_scan_help(self):
        title = self.run_type.currentText()
        message = self.plan_funcs[self.run_type.currentIndex()].__doc__
        QtGui.QMessageBox.question(self, 
                                   'Help! - {}'.format(title), 
                                   message, 
                                   QtGui.QMessageBox.Ok)

    def reset_processing_tab(self):
        self.active_threads -= 1
        self.progressBar_processing.setValue(int(np.round(100 * (self.total_threads - self.active_threads)/self.total_threads)))
        print('[Threads] Number of active threads: {}'.format(self.active_threads))

        while len(self.plotting_list) > 0:
            plot_info = self.plotting_list.pop()
            plot_info[5].plot(plot_info[0], plot_info[1], plot_info[2])
            plot_info[5].set_xlabel(plot_info[3])
            plot_info[5].set_ylabel(plot_info[4])
            if(plot_info[2] == 'ys'):
                edge_path = mpatches.Patch(facecolor='y', edgecolor = 'black', label='Edge')
                self.figure_old_scans_2.ax.legend(handles = [edge_path])
                self.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(plot_info[0], plot_info[1]), xy=(plot_info[0], plot_info[1]), textcoords='data')
            plot_info[6].draw_idle()

        if self.active_threads == 0:
            print('[ #### All Threads Finished #### ]')
            self.total_threads = 0
            self.progressBar_processing.setValue(int(np.round(100)))
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

# Class to write terminal output to screen
class EmittingStream(QtCore.QObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = sys.__stdout__.buffer
        self.close = sys.__stdout__.close
        self.closed = sys.__stdout__.closed
        self.detach = sys.__stdout__.detach
        self.encoding = sys.__stdout__.encoding
        self.errors = sys.__stdout__.errors
        self.fileno = sys.__stdout__.fileno
        self.flush = sys.__stdout__.flush
        self.isatty = sys.__stdout__.isatty
        self.line_buffering = sys.__stdout__.line_buffering
        self.mode = sys.__stdout__.mode
        self.name = sys.__stdout__.name
        self.newlines = sys.__stdout__.newlines
        self.read = sys.__stdout__.read
        self.readable = sys.__stdout__.readable
        self.readlines = sys.__stdout__.readlines
        self.seek = sys.__stdout__.seek
        self.seekable = sys.__stdout__.seekable
        #self.softspace = sys.__stdout__.softspace
        self.tell = sys.__stdout__.tell
        self.truncate = sys.__stdout__.truncate
        self.writable = sys.__stdout__.writable
        self.writelines = sys.__stdout__.writelines

    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))
        # Comment next line if the output should be printed only in the GUI
        sys.__stdout__.write(text)

#    @property
#    def plan(self):
#        lp = LivePlot(self.plot_x,
#                      self.plot_y,
#                      fig=self.fig)

#        @subs_decorator([lp])
#        def scan_gui_plan():
#            return (yield from self.plan_func(self.dets, *self.get_args()))


#def tune_factory(motor):
#    from bluesky.plans import scan
#    from collections import ChainMap

#    def tune(md=None):
#        if md is None:
#            md = {}
#        md = ChainMap(md, {'plan_name': 'tuning {}'.format(motor)})
#        yield from scan(motor, -1, 1, 100, md=md)

#    return tune

class process_bin_thread(QThread):
    def __init__(self, gui, index = 1, parent_thread = None, parser = None):
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
            while(self.parent_thread.isFinished() == False):
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

        if e0 < self.gui.figure_old_scans_2.axes[0].xaxis.get_data_interval()[0] or e0 > self.gui.figure_old_scans_2.axes[0].xaxis.get_data_interval()[1]:
            ret = self.gui.questionMessage('E0 Confirmation', 'E0 seems to be out of the scan range. Would you like to proceed?')
            if not ret:
                print ('[Binning Thread {}] Binning aborted!'.format(self.index))
                return False

        binned = self.gen_parser.bin(e0, 
                                     e0 + edge_start, 
                                     e0 + edge_end, 
                                     preedge_spacing, 
                                     xanes_spacing, 
                                     exafs_spacing)


        result = binned[self.gui.listWidget_numerator.currentItem().text()] / binned[self.gui.listWidget_denominator.currentItem().text()]
        result_orig = self.gen_parser.data_manager.data_arrays[self.gui.listWidget_numerator.currentItem().text()] / self.gen_parser.data_manager.data_arrays[self.gui.listWidget_denominator.currentItem().text()]
        ylabel = '{} / {}'.format(self.gui.listWidget_numerator.currentItem().text(), self.gui.listWidget_denominator.currentItem().text())

        if self.gui.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            result = np.log(result)
            result_orig = np.log(result_orig)
        ylabel = 'Binned {}'.format(ylabel)

        energy_string = self.gen_parser.get_energy_string()

        plot_info = [binned[energy_string], 
                     result, 
                     'r', 
                     energy_string, 
                     ylabel, 
                     self.gui.figure_old_scans_3.ax, 
                     self.gui.canvas_old_scans_3]
        self.gui.plotting_list.append(plot_info)
        

        k_data = self.gen_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         result,
                                                         self.gen_parser.data_manager.sorted_matrix[:, 0],
                                                         self.gen_parser.data_manager.data_arrays[energy_string],
                                                         result_orig,
                                                         k_power)

        #self.gui.figure_old_scans.ax.plot(k_data[0], k_data[1])
        plot_info = [k_data[0], k_data[1], '', 'k', r'$\kappa$ * k ^ {}'.format(k_power), self.gui.figure_old_scans.ax, self.gui.canvas_old_scans]
        self.gui.plotting_list.append(plot_info)

        #self.gui.figure_old_scans.ax.grid(True)
        #self.gui.figure_old_scans.ax.set_xlabel('k')
        #self.gui.figure_old_scans.ax.set_ylabel(r'$\kappa$ * k ^ {}'.format(k_power)) #'ϰ * k ^ {}'.format(k_power))
        self.gui.push_replot_exafs.setEnabled(True)
        self.gui.push_save_bin.setEnabled(True)

        if self.gui.checkBox_process_bin.checkState() > 0:
            filename = self.gen_parser.curr_filename_save
            self.gen_parser.data_manager.export_dat_gen(filename)
            print('[Binning Thread {}] File Saved! [{}]'.format(self.index, filename[:-3] + 'dat'))

        print('[Binning Thread {}] Finished'.format(self.index))




class process_bin_thread_equal(QThread):
    update_listWidgets = QtCore.pyqtSignal(list, list)#, int, int)
    create_lists = QtCore.pyqtSignal(list, list)
    def __init__(self, gui, filename, index = 1):
        QThread.__init__(self)
        self.gui = gui
        self.index = index
        self.filename = filename
        self.gen_parser = xasdata.XASdataGeneric(gui.db)
        self.gen_parser.curr_filename_save = filename

    def __del__(self):
        self.wait()

    def run(self):
        #for filename in self.gui.selected_filename_bin:
        print('[Binning Equal Thread {}] Starting...'.format(self.index))
        self.gen_parser.loadInterpFile(self.filename)
        #if self.gui.listWidget_numerator.currentItem() is not None:
        #    self.gui.last_num = self.gui.listWidget_numerator.currentRow()
        #if self.gui.listWidget_denominator.currentItem() is not None:
        #    self.gui.last_den = self.gui.listWidget_denominator.currentRow()
        #self.gui.listWidget_numerator.clear()
        #self.gui.listWidget_denominator.clear()
        #self.gui.listWidget_numerator.insertItems(0, list(self.gen_parser.interp_arrays.keys()))
        #self.gui.listWidget_denominator.insertItems(0, list(self.gen_parser.interp_arrays.keys()))

        ordered_dict = collections.OrderedDict(sorted(self.gen_parser.interp_arrays.items()))
        self.create_lists.emit(list(ordered_dict.keys()), list(ordered_dict.keys()))
        while(self.gui.listWidget_denominator.count() == 0 or self.gui.listWidget_numerator.count() == 0):
            QtCore.QCoreApplication.processEvents()
            ttime.sleep(0.1)
        
        
        #print(self.gui.listWidget_numerator.count())
        if self.gui.listWidget_numerator.count() > 0 and self.gui.listWidget_denominator.count() > 0:
            value_num = ''
            if self.gui.last_num != '' and self.gui.last_num <= len(self.gen_parser.interp_arrays.keys()) - 1:
                items_num = self.gui.last_num#self.gui.listWidget_numerator.findItems(self.gui.last_num, PyQt4.QtCore.Qt.MatchExactly)
                value_num = [items_num]
            if value_num == '':
                value_num = [2]
            
            value_den = ''
            if self.gui.last_den != '' and self.gui.last_den <= len(self.gen_parser.interp_arrays.keys()) - 1:
                items_den = self.gui.last_den
                value_den = [items_den]
            if value_den == '':
                value_den = [len(self.gen_parser.interp_arrays.keys()) - 1]

            self.update_listWidgets.emit(value_num, value_den)
            ttime.sleep(0.2)
            while(self.gui.listWidget_denominator.currentRow() == -1 or self.gui.listWidget_numerator.currentRow() == -1):
                QtCore.QCoreApplication.processEvents()
                ttime.sleep(0.1)

            energy_string = self.gen_parser.get_energy_string()

            result = self.gen_parser.interp_arrays[self.gui.listWidget_numerator.currentItem().text()][:, 1] / self.gen_parser.interp_arrays[self.gui.listWidget_denominator.currentItem().text()][:, 1]
            ylabel = '{} / {}'.format(self.gui.listWidget_numerator.currentItem().text(), self.gui.listWidget_denominator.currentItem().text())

            if self.gui.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                result = np.log(result)
            
            plot_info = [self.gen_parser.interp_arrays[energy_string][:, 1], 
                         result, 
                         'b', 
                         energy_string, 
                         ylabel, 
                         self.gui.figure_old_scans_3.ax, 
                         self.gui.canvas_old_scans_3]
            self.gui.plotting_list.append(plot_info)


            bin_eq = self.gen_parser.bin_equal()

            result = bin_eq[self.gui.listWidget_numerator.currentItem().text()] / bin_eq[self.gui.listWidget_denominator.currentItem().text()]
            ylabel = '{} / {}'.format(self.gui.listWidget_numerator.currentItem().text(), self.gui.listWidget_denominator.currentItem().text())

            if self.gui.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                result = np.log(result)
            ylabel = 'Binned Equally {}'.format(ylabel)

            plot_info = [bin_eq[energy_string], 
                         result, 
                         'b', 
                         energy_string, 
                         ylabel, 
                         self.gui.figure_old_scans_2.ax, 
                         self.gui.canvas_old_scans_2]
            self.gui.plotting_list.append(plot_info)



            if self.gui.checkBox_find_edge.checkState() > 0:

                self.gui.edge_index = self.gen_parser.data_manager.get_edge_index(result)
                if self.gui.edge_index > 0:
                    
                    x_edge = self.gen_parser.data_manager.en_grid[self.gui.edge_index]
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

                    print('[Binning Equal Thread {}] Edge: '.format(self.index) + str(int(np.round(self.gen_parser.data_manager.en_grid[self.gui.edge_index]))))
                    self.gui.edit_E0_2.setText(str(int(np.round(self.gen_parser.data_manager.en_grid[self.gui.edge_index]))))
                

            result_der = self.gen_parser.data_manager.get_derivative(result)
            plot_info = [bin_eq[energy_string], 
                         result_der, 
                         'r', energy_string, 
                         'Derivative', 
                         self.gui.figure_old_scans_2.ax2, 
                         self.gui.canvas_old_scans_2]
            self.gui.plotting_list.append(plot_info)

            #self.gui.figure_old_scans_2.ax2.set_ylabel('Derivative', color='r')

        print('[Binning Equal Thread {}] Finished'.format(self.index))


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
            process_thread_equal = process_bin_thread_equal(self.gui, filename, index) 
            self.gui.connect(process_thread_equal, SIGNAL("finished()"), self.gui.reset_processing_tab)
            process_thread_equal.update_listWidgets.connect(self.gui.update_listWidgets)
            process_thread_equal.create_lists.connect(self.gui.create_lists)
            process_thread_equal.start()
            self.gui.active_threads += 1
            self.gui.total_threads += 1
            #self.gui.progressBar_processing.setValue(int(np.round(100 * (self.gui.total_threads - self.gui.active_threads)/self.gui.total_threads)))

            self.gui.curr_filename_save = filename
            if self.gui.checkBox_process_bin.checkState() > 0:
                process_thread = process_bin_thread(self.gui, index, process_thread_equal, process_thread_equal.gen_parser) 
                self.gui.connect(process_thread, SIGNAL("finished()"), self.gui.reset_processing_tab)
                process_thread.start()
                self.gui.active_threads += 1
                self.gui.total_threads += 1
            index += 1
        self.gui.gen_parser = process_thread_equal.gen_parser


class piezo_fb_thread(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui
        self.go = 0

    def gauss(self, x, *p):
        A, mu, sigma = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2))

    def gaussian_piezo_feedback(self, line = 420, center_point = 655):
        image = []
        image = self.gui.bpm_es.image.read()['bpm_es_image_array_data']['value'].reshape((960,1280))
        image = image.transpose()

        index_max = image[:, 960 - line].argmax()
        max_value = image[:, 960 - line].max()

        if max_value >= 10 and max_value <= 100:
            coeff, var_matrix = curve_fit(self.gauss, list(range(1280)), image[:, 960-line], p0=[1, index_max, 5])
            #print('Index: {}     coeff[1]: {}'.format(index_max, coeff[1]))
            deviation = -(coeff[1] - center_point)
            piezo_diff = deviation * 0.0855
            curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
            self.gui.hhm.pitch.move(curr_value + piezo_diff)

    def run(self):
        self.go = 1
        while(self.go):
            if self.gui.shutter_a.state.value == 0 and self.gui.shutter_b.state.value == 0:
                self.gaussian_piezo_feedback(line = self.gui.piezo_line, center_point = self.gui.piezo_center)
                ttime.sleep(0.001)






