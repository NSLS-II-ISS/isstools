import numpy as np
from PyQt4 import uic, QtGui, QtCore
from PyQt4.QtCore import QThread, SIGNAL
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import matplotlib.patches as mpatches
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
from isstools.dialogs import UpdateAngleOffset
from isstools.conversions import xray
import os
from os import listdir
from os.path import isfile, join
import inspect
import re
import sys

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
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.fig = fig = self.figure_content()
        self.addCanvas()
        self.run_start.clicked.connect(self.run_scan)
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

        # Initialize 'run' tab
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.run_type.addItems(self.plan_funcs_names)
        self.push_re_abort.clicked.connect(self.re_abort)
        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_re_state)
        self.timer.start(1000)

        self.run_type.currentIndexChanged.connect(self.populateParams)
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.populateParams(0)

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

        # Redirect terminal output to GUI
        sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
        sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

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
        self.abs_parser.data_manager.export_dat(filename, self.abs_parser.header_read.replace('Timestamp (s)   ','', 1)[:-1])
        print('[Save File] File Saved! [{}]'.format(filename[:-3] + 'dat'))

    def calibrate_offset(self):
        ret = self.questionMessage('Confirmation', 'Are you sure you would like to calibrate it?')
        if not ret:
            print ('[E0 Calibration] Aborted!')
            return False
        self.RE.md['angle_offset'] = str(float(self.RE.md['angle_offset']) - (xray.energy2encoder(float(self.edit_E0_2.text())) - xray.energy2encoder(float(self.edit_ECal.text())))/360000)
        self.label_angle_offset.setText('{0:.4f}'.format(float(self.RE.md['angle_offset'])))
        print ('[E0 Calibration] New value: {}\n[E0 Calibration] Completed!'.format(self.RE.md['angle_offset']))

    def get_dic(self, module):
        dic = dict()
        if self.checkBox_num_i0.checkState() > 0:
            dic['numerator'] = module.i0_interp
            if(hasattr(module, 'data_i0')):
                dic['original_numerator'] = module.data_i0
        elif self.checkBox_num_it.checkState() > 0:
            dic['numerator'] = module.it_interp
            if(hasattr(module, 'data_it')):
                dic['original_numerator'] = module.data_it
        elif self.checkBox_num_ir.checkState() > 0:
            dic['numerator'] = module.ir_interp
            if(hasattr(module, 'data_ir')):
                dic['original_numerator'] = module.data_ir
        elif self.checkBox_num_if.checkState() > 0:
            dic['numerator'] = module.iff_interp
            if(hasattr(module, 'data_iff')):
                dic['original_numerator'] = module.data_iff
        elif self.checkBox_num_1.checkState() > 0:
            if len(module.i0_interp.shape) > 1:
                array_ones = np.copy(module.i0_interp)
                array_ones[:,1] = np.ones(len(module.i0_interp[:,0]))
            else:
                array_ones = np.ones(len(module.i0_interp))
            dic['numerator'] = array_ones

            if(hasattr(module, 'data_i0')):
                if len(module.data_i0.shape) > 1:
                    array_ones = np.copy(module.data_i0)
                    array_ones[:,1] = np.ones(len(module.data_i0[:,0]))
                else:
                    array_ones = np.ones(len(module.data_i0))
                    dic['original_numerator'] = module.data_i0
            dic['original_numerator'] = array_ones

        if self.checkBox_den_i0.checkState() > 0:
            dic['denominator'] = module.i0_interp
            if(hasattr(module, 'data_i0')):
                dic['original_denominator'] = module.data_i0
        elif self.checkBox_den_it.checkState() > 0:
            dic['denominator'] = module.it_interp
            if(hasattr(module, 'data_it')):
                dic['original_denominator'] = module.data_it
        elif self.checkBox_den_ir.checkState() > 0:
            dic['denominator'] = module.ir_interp
            if(hasattr(module, 'data_ir')):
                dic['original_denominator'] = module.data_ir
        elif self.checkBox_den_if.checkState() > 0:
            dic['denominator'] = module.iff_interp
            if(hasattr(module, 'data_iff')):
                dic['original_denominator'] = module.data_iff
        elif self.checkBox_den_1.checkState() > 0:
            if len(module.i0_interp.shape) > 1:
                array_ones = np.copy(module.i0_interp)
                array_ones[:,1] = np.ones(len(module.i0_interp[:,0]))
            else:
                array_ones = np.ones(len(module.i0_interp))
            dic['denominator'] = array_ones

            if(hasattr(module, 'data_i0')):
                if len(module.data_i0.shape) > 1:
                    array_ones = np.copy(module.data_i0)
                    array_ones[:,1] = np.ones(len(module.data_i0[:,0]))
                else:
                    array_ones = np.ones(len(module.data_i0))
                    dic['original_denominator'] = module.data_i0
            dic['original_denominator'] = array_ones

        if self.checkBox_log.checkState() > 0:
            dic['log'] = True
        else:
            dic['log'] = False

        return dic

    def update_k_view(self):
        e0 = int(self.edit_E0_2.text())
        edge_start = int(self.edit_edge_start.text())
        edge_end = int(self.edit_edge_end.text())
        preedge_spacing = float(self.edit_preedge_spacing.text())
        xanes_spacing = float(self.edit_xanes_spacing.text())
        exafs_spacing = float(self.edit_exafs_spacing.text())
        k_power = float(self.edit_y_power.text())

        k_data = self.abs_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         self.abs_parser.data_manager.abs,
                                                         self.abs_parser.data_manager.sorted_matrix[:, 1],
                                                         self.abs_parser.data_manager.data_en,
                                                         self.abs_parser.data_manager.abs_orig,
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
        dic = self.get_dic(self.abs_parser)
        self.abs_parser.plot(plotting_dic = dic, 
                             ax = self.figure_old_scans_3.ax, 
                             color = 'b')

        self.figure_old_scans_2.ax.cla()
        self.figure_old_scans_2.ax2.cla()
        self.canvas_old_scans_2.draw_idle()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        #self.abs_parser.bin_equal()
        dic = self.get_dic(self.abs_parser.data_manager)
        self.abs_parser.data_manager.plot(plotting_dic = dic, 
                                          ax = self.figure_old_scans_2.ax, 
                                          color = 'b')
        self.figure_old_scans_2.ax.set_ylabel('Log(i0/it)', color='b')
        self.edge_index = self.abs_parser.data_manager.get_edge_index(self.abs_parser.data_manager.abs)
        if self.edge_index > 0:
            x_edge = self.abs_parser.data_manager.en_grid[self.edge_index]
            y_edge = self.abs_parser.data_manager.abs[self.edge_index]

            self.figure_old_scans_2.ax.plot(x_edge, y_edge, 'ys')
            edge_path = mpatches.Patch(facecolor='y', edgecolor = 'black', label='Edge')
            self.figure_old_scans_2.ax.legend(handles = [edge_path])
            self.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(x_edge, y_edge), xy=(x_edge, y_edge), textcoords='data')
            print('Edge: ' + str(int(np.round(self.abs_parser.data_manager.en_grid[self.edge_index]))))
            self.edit_E0_2.setText(str(int(np.round(self.abs_parser.data_manager.en_grid[self.edge_index]))))
        
        self.abs_parser.data_manager.plot_der(plotting_dic = dic, ax = self.figure_old_scans_2.ax2, color = 'r')
        self.figure_old_scans_2.ax2.set_ylabel('Derivative', color='r')

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
        t_manager = process_threads_manager(self)
        t_manager.start()
        print('[Finished Launching Threads]')

        #for filename in self.selected_filename_bin:
        #    process_thread_equal = process_bin_thread_equal(self, filename, index) 
        #    process_thread_equal.start()

        #    self.curr_filename_save = filename
        #    if self.checkBox_process_bin.checkState() > 0:
        #        process_thread = process_bin_thread(self, index, process_thread_equal, process_thread_equal.abs_parser) 
        #        process_thread.start()

        #    index += 1

        #self.push_bin.setEnabled(True)
        #self.push_replot_exafs.setDisabled(True)
        #self.push_save_bin.setDisabled(True)
        #self.push_replot_file.setEnabled(True)

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
        rows = int(self.gridLayout_13.count()/3)
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
        self.plot_tune.addWidget(self.canvas_tune)
        self.canvas_tune.draw_idle()

        self.figure_gen_scan = Figure()
        self.figure_gen_scan.set_facecolor(color='0.89')
        self.canvas_gen_scan = FigureCanvas(self.figure_gen_scan)
        self.figure_gen_scan.ax = self.figure_gen_scan.add_subplot(111)
        self.plot_gen_scan.addWidget(self.canvas_gen_scan)
        self.canvas_gen_scan.draw_idle()

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

        self.comment = self.params2[0].text()
        if(self.comment):
            print('\nStarting scan...')

            # Get parameters from the widgets and organize them in a tuple (run_params)
            run_params = ()
            for i in range(len(self.params1)):
                if (self.param_types[i] == int):
                    run_params += (self.params2[i].value(),)
                elif (self.param_types[i] == float):
                    run_params += (self.params2[i].value(),)
                elif (self.param_types[i] == bool):
                    run_params += (bool(self.params2[i].checkState()),)
                elif (self.param_types[i] == str):
                    run_params += (self.params2[i].text(),)
            
            # Erase last graph
            self.figure.ax.cla()
            self.canvas.draw_idle()

            # Run the scan using the tuple created before
            self.current_uid, self.current_filepath, absorp = self.plan_funcs[self.run_type.currentIndex()](*run_params, ax=self.figure.ax)

            if absorp == True:
                self.parser = xasdata.XASdataAbs()
                self.parser.loadInterpFile(self.current_filepath)
                self.parser.plot(ax = self.figure.ax)
            elif absorp == False:
                self.parser = xasdata.XASdataFlu()
                self.parser.loadInterpFile(self.current_filepath)
                xia_filename = self.db[self.current_uid]['start']['xia_filename']
                xia_filepath = 'smb://elistavitski-ni/epics/{}'.format(xia_filename)
                xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                smbclient.copy()
                xia_parser = self.xia_parser
                xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                xia_parsed_filepath = self.current_filepath[0 : self.current_filepath.rfind('/') + 1]
                xia_parser.export_files(dest_filepath = xia_parsed_filepath, all_in_one = True)
            # Fix that later
                length = min(len(xia_parser.exporting_array1), len(self.parser.energy_interp))
                #xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 1, 6.7, 6.9, self.figure.ax, self.parser.energy_interp)
                #xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 2, 6.7, 6.9, self.figure.ax, self.parser.energy_interp)
                #xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 3, 6.7, 6.9, self.figure.ax, self.parser.energy_interp)
                #xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 4, 6.7, 6.9, self.figure.ax, self.parser.energy_interp)

                #workaround
                mca1 = xia_parser.parse_roi(range(0, length), 1, 4.8, 5.1)
                mca2 = xia_parser.parse_roi(range(0, length), 2, 4.8, 5.1)
                mca3 = xia_parser.parse_roi(range(0, length), 3, 4.8, 5.1)
                mca4 = xia_parser.parse_roi(range(0, length), 4, 4.8, 5.1)
                mca_sum = mca1 + mca2 + mca3 + mca4
                ts = self.parser.energy_interp[:,0]
                energy_interp = self.parser.energy_interp[:,1]
                i0_interp = self.parser.i0_interp[:,1]
                it_interp = self.parser.it_interp[:,1]
                ir_interp = self.parser.ir_interp[:,1]
                iff_interp = self.parser.iff_interp[:,1]

                print(len(energy_interp), len(mca_sum), len(i0_interp))
                self.figure.ax.plot(energy_interp, -(mca_sum/i0_interp))
                self.canvas.draw_idle()

                np.savetxt(self.current_filepath[:-4] + '-2.txt', np.array([ts, energy_interp, i0_interp, it_interp, iff_interp, ir_interp, mca_sum]).transpose(), header='time    energy    i0    it    iff    ir    XIA_SUM', fmt = '%f %f %f %f %f %f %d')
                #workaround end

            if absorp != '' and type(absorp) == bool:
                self.figure.ax.set_title(self.comment)

                self.log_path = self.current_filepath[0 : self.current_filepath.rfind('/') + 1] + 'log/'
                if(not os.path.exists(self.log_path)):
                    os.makedirs(self.log_path)

                self.snapshots_path = self.log_path + 'snapshots/'
                if(not os.path.exists(self.snapshots_path)):
                    os.makedirs(self.snapshots_path)

                self.file_path = 'snapshots/' + self.comment + '.png'
                fn = self.log_path + self.file_path
                repeat = 1
                while(os.path.isfile(fn)):
                    repeat += 1
                    self.file_path = 'snapshots/' + self.comment + '-' + str(repeat) + '.png'
                    fn = self.log_path + self.file_path
                self.figure.savefig(fn)


                if self.checkBox_auto_process.checkState() > 0 and self.active_threads == 0: # Change to a control
                    self.tabWidget.setCurrentIndex(4)
                    self.selected_filename_bin = [self.current_filepath]
                    self.label_24.setText(self.current_filepath)
                    self.process_bin_equal()

                # Check saturation:
                if absorp == True:
                    try: 
                        warnings = ()
                        if np.max(np.abs(self.parser.i0_interp[:,1])) > 3.9:
                            warnings += ('"i0" seems to be saturated',) #(values > 3.9 V), please change the ion chamber gain',)
                        if np.max(np.abs(self.parser.it_interp[:,1])) > 3.9:
                            warnings += ('"it" seems to be saturated',) #(values > 3.9 V), please change the ion chamber gain',)
                        if np.max(np.abs(self.parser.ir_interp[:,1])) > 9.9:
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
    def __init__(self, gui, index = 1, parent_thread = None, abs_parser = None):
        QThread.__init__(self)
        self.gui = gui
        self.parent_thread = parent_thread
        self.index = index
        if abs_parser is None:
            self.abs_parser = self.gui.abs_parser
        else:
            self.abs_parser = abs_parser

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

        self.abs_parser.bin(e0, 
                            e0 + edge_start, 
                            e0 + edge_end, 
                            preedge_spacing, 
                            xanes_spacing, 
                            exafs_spacing)

        dic = self.gui.get_dic(self.abs_parser.data_manager)

        #while(self.gui.old_scans_3_control != self.index):
        #    ttime.sleep(.01)
        plot_info = self.abs_parser.data_manager.get_plot_info(plotting_dic = dic, ax = self.gui.figure_old_scans_3.ax, color = 'r')
        plot_info.append(self.gui.canvas_old_scans_3)
        self.gui.plotting_list.append(plot_info)
        #self.gui.canvas_old_scans_3.draw_idle()
        self.gui.old_scans_3_control += 1
        

        k_data = self.abs_parser.data_manager.get_k_data(e0,
                                                         edge_end,
                                                         exafs_spacing,
                                                         self.abs_parser.data_manager.abs,
                                                         self.abs_parser.data_manager.sorted_matrix[:, 1],
                                                         self.abs_parser.data_manager.data_en,
                                                         self.abs_parser.data_manager.abs_orig,
                                                         k_power)

        while(self.gui.old_scans_control != self.index):
            ttime.sleep(.01)

        self.gui.figure_old_scans.ax.plot(k_data[0], k_data[1])
        plot_info = [k_data[0], k_data[1], '', 'k', r'$\kappa$ * k ^ {}'.format(k_power), self.gui.figure_old_scans.ax, self.gui.canvas_old_scans]
        self.gui.plotting_list.append(plot_info)

        #self.gui.figure_old_scans.ax.grid(True)
        #self.gui.figure_old_scans.ax.set_xlabel('k')
        #self.gui.figure_old_scans.ax.set_ylabel(r'$\kappa$ * k ^ {}'.format(k_power)) #'ϰ * k ^ {}'.format(k_power))
        #self.gui.canvas_old_scans.draw_idle()
        self.gui.old_scans_control += 1
        self.gui.push_replot_exafs.setEnabled(True)
        self.gui.push_save_bin.setEnabled(True)

        if self.gui.checkBox_process_bin.checkState() > 0:
            filename = self.abs_parser.curr_filename_save
            self.abs_parser.data_manager.export_dat(filename, self.abs_parser.header_read.replace('Timestamp (s)   ','', 1)[:-1])
            print('[Binning Thread {}] File Saved! [{}]'.format(self.index, filename[:-3] + 'dat'))

        print('[Binning Thread {}] Finished'.format(self.index))

        #optionally: Emit signal



class process_bin_thread_equal(QThread):
    def __init__(self, gui, filename, index = 1):
        QThread.__init__(self)
        self.gui = gui
        self.index = index
        self.filename = filename
        self.abs_parser = xasdata.XASdataAbs()
        self.abs_parser.curr_filename_save = filename

    def __del__(self):
        self.wait()

    def run(self):
        #for filename in self.gui.selected_filename_bin:
        print('[Binning Equal Thread {}] Starting...'.format(self.index))
        self.abs_parser.loadInterpFile(self.filename) #self.gui.label_24.text())

        while(self.gui.old_scans_3_control != self.index):
            ttime.sleep(.01)

        dic = self.gui.get_dic(self.abs_parser)
        plot_info = self.abs_parser.get_plot_info(plotting_dic = dic, ax = self.gui.figure_old_scans_3.ax, color = 'b')
        plot_info.append(self.gui.canvas_old_scans_3)
        self.gui.plotting_list.append(plot_info)

        #self.gui.canvas_old_scans_3.draw_idle()
        #self.gui.old_scans_3_control += 1


        self.abs_parser.bin_equal()
        dic = self.gui.get_dic(self.abs_parser.data_manager)
        while(self.gui.old_scans_2_control != self.index):
            ttime.sleep(.01)

        plot_info = self.abs_parser.data_manager.get_plot_info(plotting_dic = dic, ax = self.gui.figure_old_scans_2.ax, color = 'b')
        plot_info.append(self.gui.canvas_old_scans_2)
        self.gui.plotting_list.append(plot_info)
        #self.gui.figure_old_scans_2.ax.set_ylabel('Log(i0/it)', color='b')

        if self.gui.checkBox_find_edge.checkState() > 0:
            self.gui.edge_index = self.abs_parser.data_manager.get_edge_index(self.abs_parser.data_manager.abs)
            if self.gui.edge_index > 0:
                x_edge = self.abs_parser.data_manager.en_grid[self.gui.edge_index]
                y_edge = self.abs_parser.data_manager.abs[self.gui.edge_index]

                self.gui.figure_old_scans_2.ax.plot(x_edge, y_edge, 'ys')
                plot_info = [x_edge, y_edge, 'ys', '', '', self.gui.figure_old_scans_2.ax, self.gui.canvas_old_scans_2]
                self.gui.plotting_list.append(plot_info)
                #edge_path = mpatches.Patch(facecolor='y', edgecolor = 'black', label='Edge')
                #self.gui.figure_old_scans_2.ax.legend(handles = [edge_path])
                #self.gui.figure_old_scans_2.ax.annotate('({0:.2f}, {1:.2f})'.format(x_edge, y_edge), xy=(x_edge, y_edge), textcoords='data')
                print('[Binning Equal Thread {}] Edge: '.format(self.index) + str(int(np.round(self.abs_parser.data_manager.en_grid[self.gui.edge_index]))))
                self.gui.edit_E0_2.setText(str(int(np.round(self.abs_parser.data_manager.en_grid[self.gui.edge_index]))))
            
        plot_info = self.abs_parser.data_manager.get_plotder_info(plotting_dic = dic, ax = self.gui.figure_old_scans_2.ax2, color = 'r')
        plot_info.append(self.gui.canvas_old_scans_2)
        self.gui.plotting_list.append(plot_info)
        #self.gui.figure_old_scans_2.ax2.set_ylabel('Derivative', color='r')

        #self.gui.canvas_old_scans_2.draw_idle()
        self.gui.old_scans_2_control += 1
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
            process_thread_equal.start()
            self.gui.active_threads += 1
            self.gui.total_threads += 1
            #self.gui.progressBar_processing.setValue(int(np.round(100 * (self.gui.total_threads - self.gui.active_threads)/self.gui.total_threads)))

            self.gui.curr_filename_save = filename
            if self.gui.checkBox_process_bin.checkState() > 0:
                process_thread = process_bin_thread(self.gui, index, process_thread_equal, process_thread_equal.abs_parser) 
                self.gui.connect(process_thread, SIGNAL("finished()"), self.gui.reset_processing_tab)
                process_thread.start()
                self.gui.active_threads += 1
                self.gui.total_threads += 1
            index += 1
        self.gui.abs_parser = process_thread_equal.abs_parser



