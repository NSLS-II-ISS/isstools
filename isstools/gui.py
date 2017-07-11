import numpy as np
#import PyQt5
from PyQt5 import uic, QtGui, QtCore, Qt, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QSettings
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.widgets import Cursor
import matplotlib.patches as mpatches
from scipy.optimize import curve_fit

import pkg_resources
import time as ttime
import math
from subprocess import call

from ophyd import (Component as Cpt, EpicsSignal, EpicsSignalRO, EpicsMotor)

from isstools.trajectory.trajectory  import trajectory
from isstools.trajectory.trajectory import trajectory_manager
from isstools.xasdata import xasdata
from isstools.xiaparser import xiaparser
from isstools.elements import elements
from isstools.dialogs import UpdateUserDialog
from isstools.dialogs import UpdatePiezoDialog
from isstools.dialogs import UpdateAngleOffset
from isstools.dialogs import MoveMotorDialog
from isstools.dialogs import Prepare_BL_Dialog
from isstools.conversions import xray
from isstools.pid import PID
from isstools.batch.batch import BatchManager
import os
from os import listdir
from os.path import isfile, join
import inspect
import re
import sys
import collections
import signal

import json
import pandas as pd
import warnings

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

#class ScanGui(QtWidgets.QMainWindow):
class ScanGui(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs = [], tune_funcs = [], prep_traj_plan = None, RE = None, db = None, hhm = None, shutters = {}, det_dict = {}, motors_list = [], general_scan_func = None, parent=None, *args, **kwargs):


        if 'write_html_log' in kwargs:
            self.html_log_func = kwargs['write_html_log']
            del kwargs['write_html_log']
        else:
            self.html_log_func = None

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        print(QtWidgets.QApplication.instance())

        self.addCanvas()
        self.run_start.clicked.connect(self.run_scan)
        self.prep_traj_plan = prep_traj_plan
        if self.prep_traj_plan is None:
            self.push_prepare_trajectory.setEnabled(False)
        self.RE = RE
        if self.RE is not None:
            self.RE.last_state = ''
            # Write metadata in the GUI
            self.label_angle_offset.setText('{0:.4f}'.format(float(RE.md['angle_offset'])))
            self.label_6.setText('{}'.format(RE.md['year']))
            self.label_7.setText('{}'.format(RE.md['cycle']))
            self.label_8.setText('{}'.format(RE.md['PROPOSAL']))
            self.label_9.setText('{}'.format(RE.md['SAF']))
            self.label_10.setText('{}'.format(RE.md['PI']))
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)
        else:
            self.push_update_offset.setEnabled(False)
            self.push_calibrate.setEnabled(False)
            self.push_update_user.setEnabled(False)
            self.push_re_abort.setEnabled(False)
            self.run_start.setEnabled(False)
            self.run_check_gains.setEnabled(False)
            self.tabWidget.setTabEnabled(1, False)

        self.db = db
        if self.db is None:
            self.run_start.setEnabled(False)
        self.gen_parser = xasdata.XASdataGeneric(self.db)
        self.push_update_user.clicked.connect(self.update_user)
        self.det_dict = det_dict

        self.motors_list = motors_list
        self.gen_scan_func = general_scan_func

        # Initialize 'trajectory' tab
        self.hhm = hhm
        if self.hhm is not None:
            self.hhm.trajectory_progress.subscribe(self.update_progress)
            self.progress_sig.connect(self.update_progressbar) 
            self.progressBar.setValue(0)
            self.traj_manager = trajectory_manager(hhm)
            self.comboBox_2.addItems(['1', '2', '3', '4', '5', '6', '7', '8'])
            self.comboBox_3.addItems(['1', '2', '3', '4', '5', '6', '7', '8'])
            self.comboBox_3.setCurrentIndex(self.traj_manager.current_lut() - 1)
            self.trajectories = self.traj_manager.read_info(silent=True)
            self.trajectories = collections.OrderedDict(sorted(self.trajectories.items()))
            self.update_batch_traj()

            self.fb_master = 0
            self.piezo_line = int(self.hhm.fb_line.value)
            self.piezo_center = float(self.hhm.fb_center.value)
            self.piezo_nlines = int(self.hhm.fb_nlines.value)
            self.piezo_nmeasures = int(self.hhm.fb_nmeasures.value)
            self.piezo_kp = float(self.hhm.fb_pcoeff.value)
            self.hhm.fb_status.subscribe(self.update_fb_status)
        else:
            self.tabWidget.setTabEnabled(0, False)
            self.tabWidget.setTabEnabled(4, False)
            self.checkBox_piezo_fb.setEnabled(False)
            self.update_piezo.setEnabled(False)

        self.traj_creator = trajectory()
        self.trajectory_path = '/GPFS/xf08id/trajectory/'
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
        json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        self.json_data = json.loads(json_data)
        self.comboBoxElement.currentIndexChanged.connect(self.update_combo_edge)
        self.comboBoxEdge.currentIndexChanged.connect(self.update_e0_value)
        elems = [item['name'] for item in self.json_data]
        for i in range(21, 109):
            elems[i - 21] = '{:3d} {}'.format(i, elems[i - 21])
        self.comboBoxElement.addItems(elems)
        self.checkBox_traj_single_dir.stateChanged.connect(self.update_repetitions_spinbox)
        self.checkBox_traj_single_dir.stateChanged.connect(self.checkBox_traj_revert.setEnabled)


        json_data = open(pkg_resources.resource_filename('isstools', 'beamline_preparation.json')).read()
        self.json_blprep = json.loads(json_data)
        self.beamline_prep = self.json_blprep[0]
        self.fb_positions = self.json_blprep[1]['FB Positions']
        #curr_energy = 5500
        #for pv, value in [ran['pvs'] for ran in self.json_blprep[0] if ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy][0].items():


        # Initialize XIA tab
        self.xia_parser = xiaparser.xiaparser()
        self.push_gain_matching.clicked.connect(self.run_gain_matching)

        regex = re.compile('xia\d{1}')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.xia_list = [x for x in self.det_dict if x.name in matches]
        if self.xia_list == []:
            self.tabWidget.setTabEnabled(2, False)
            self.xia = None
        else:
            self.xia = self.xia_list[0]

        # Looking for analog pizzaboxes:
        regex = re.compile('pba\d{1}.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.adc_list = [x for x in self.det_dict if x.name in matches]
        
        # Looking for encoder pizzaboxes:
        regex = re.compile('pb\d{1}_enc.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.enc_list = [x for x in self.det_dict if x.name in matches]


        # Initialize 'tune' tab
        self.push_tune.clicked.connect(self.run_tune)
        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.tune_funcs = tune_funcs
        self.tune_funcs_names = [tune.__name__ for tune in tune_funcs]
        self.comboBox_4.addItems(self.tune_funcs_names)
        if len(self.tune_funcs_names) == 0:
            self.push_tune.setEnabled(0) # Disable tune if no functions are passed
        self.det_list = [det.dev_name.value if hasattr(det, 'dev_name') else det.name for det in det_dict.keys()]
        self.det_sorted_list = self.det_list
        self.det_sorted_list.sort()
        self.mot_list = [motor.name for motor in self.motors_list]
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()
        self.comboBox_gen_det.addItems(self.det_sorted_list)
        self.comboBox_gen_mot.addItems(self.mot_sorted_list)
        self.comboBox_gen_det.currentIndexChanged.connect(self.process_detsig)
        self.process_detsig()
        found_bpm = 0
        for i in range(self.comboBox_gen_det.count()):
            if 'bpm_es' == list(self.det_dict.keys())[i].name:
                self.bpm_es = list(self.det_dict.keys())[i]
                found_bpm = 1
                break     
        if found_bpm == 0 or self.hhm is None:
            self.checkBox_piezo_fb.setEnabled(False)
            self.update_piezo.setEnabled(False)
            if self.run_start.isEnabled() == False:
                self.tabWidget.setTabEnabled(3, False)
        if len(self.mot_sorted_list) == 0 or len(self.det_sorted_list) == 0 or self.gen_scan_func == None:
            self.push_gen_scan.setEnabled(0)
        if not self.push_gen_scan.isEnabled() and not self.push_tune.isEnabled():
            self.tabWidget.setTabEnabled(1, False)

        # Initialize persistent values
        self.settings = QSettings('ISS Beamline', 'XLive')
        self.edit_E0_2.setText(self.settings.value('e0_processing', defaultValue = '11470', type = str))
        self.edit_E0_2.textChanged.connect(self.save_e0_processing_value)

        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        # Initialize 'run' tab
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.run_type.addItems(self.plan_funcs_names)
        self.run_check_gains.clicked.connect(self.run_gains_test)
        self.run_check_gains_scan.clicked.connect(self.run_gains_test_scan)
        self.push_re_abort.clicked.connect(self.re_abort)
        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)
        self.push_prepare_bl.clicked.connect(self.prepare_bl_dialog)
        self.checkBox_piezo_fb.stateChanged.connect(self.enable_fb)#toggle_piezo_fb)

        if self.hhm is not None:
            self.piezo_thread = piezo_fb_thread(self)
        self.update_piezo.clicked.connect(self.update_piezo_params)
        self.push_update_piezo_center.clicked.connect(self.update_piezo_center)

        self.run_type.currentIndexChanged.connect(self.populateParams)
        self.params1 = []
        self.params2 = []
        self.params3 = []
        if len(self.plan_funcs) != 0:
            self.populateParams(0)

        if len(self.adc_list):
            times_arr = np.array(list(self.adc_list[0].averaging_points.enum_strs))
            times_arr[times_arr == ''] = 0.0
            times_arr = list(times_arr.astype(np.float) * self.adc_list[0].sample_rate.value / 100000)
            times_arr = [str(elem) for elem in times_arr]
            self.comboBox_samp_time.addItems(times_arr)
            self.comboBox_samp_time.setCurrentIndex(self.adc_list[0].averaging_points.value)

        if len(self.enc_list):
            self.lineEdit_samp_time.setText(str(self.enc_list[0].filter_dt.value / 100000))
        
        if hasattr(self.xia, 'input_trigger'):
            if self.xia.input_trigger is not None:
                self.xia.input_trigger.unit_sel.put(1) # ms, not us
                self.lineEdit_xia_samp.setText(str(self.xia.input_trigger.period_sp.value))

        # Initialize Ophyd elements
        self.shutters_sig.connect(self.change_shutter_color)
        self.shutters = shutters

        self.fe_shutters = [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'FE']
        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'FE']:
            del self.shutters[shutter.name]

        self.shutters_buttons = []
        for key, item in zip(self.shutters.keys(), self.shutters.items()):
            self.shutter_layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(key)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.shutter_layout.addWidget(label)
            label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

            button = QtWidgets.QPushButton('')
            button.setFixedSize(self.height() * 0.06, self.height() * 0.06)
            self.shutter_layout.addWidget(button)
            #button.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

            self.horizontalLayout_shutters.addLayout(self.shutter_layout)

            self.shutters_buttons.append(button)
            button.setFixedWidth(button.height() * 1.2)
            QtCore.QCoreApplication.processEvents()

            if hasattr(item[1].state, 'subscribe'):
                item[1].button = button
                item[1].state.subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if int(shutter.state.value):
                            shutter.open()
                        else:
                            shutter.close()
                    return toggle_shutter
                button.clicked.connect(toggle_shutter_call(item[1]))

                if item[1].state.value == 0:
                    button.setStyleSheet("background-color: lime")
                else:
                    button.setStyleSheet("background-color: red")

            elif hasattr(item[1], 'subscribe'):
                item[1].output.parent.button = button
                item[1].subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if shutter.state == 'closed':
                            shutter.open()
                        else:
                            shutter.close()
                    return toggle_shutter

                if item[1].state == 'closed':
                    button.setStyleSheet("background-color: red")
                elif item[1].state == 'open':
                    button.setStyleSheet("background-color: lime")

                button.clicked.connect(toggle_shutter_call(item[1]))

        if self.horizontalLayout_shutters.count() <= 1:
            self.groupBox_shutters.setVisible(False)


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


        # Initialize 'Batch Mode' tab
        self.uids_to_process = []
        self.treeView_batch = elements.TreeView(self, 'all')
        self.treeView_samples_loop = elements.TreeView(self, 'sample')
        self.treeView_samples_loop_scans = elements.TreeView(self, 'scan')
        self.treeView_samples = elements.TreeView(self, 'sample')
        self.treeView_scans = elements.TreeView(self, 'scan')
        self.push_batch_delete_all.clicked.connect(self.delete_all_batch)
        self.gridLayout_22.addWidget(self.treeView_samples_loop, 1, 0)
        self.gridLayout_22.addWidget(self.treeView_samples_loop_scans, 1, 1)
        self.gridLayout_23.addWidget(self.treeView_samples, 0, 0)
        self.gridLayout_24.addWidget(self.treeView_batch, 0, 0)
        self.gridLayout_26.addWidget(self.treeView_scans, 0, 0)
        self.treeView_batch.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        #self.treeView_samples.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.treeView_samples.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.treeView_scans.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.treeView_samples_loop.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.treeView_samples_loop_scans.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.batch_running = False
        self.batch_pause = False
        self.batch_abort = False
        self.batch_results = {}
        self.push_batch_pause.clicked.connect(self.pause_unpause_batch)
        self.push_batch_abort.clicked.connect(self.abort_batch)
        self.push_replot_batch.clicked.connect(self.plot_batches)
        self.last_num_batch_text = 'i0'
        self.last_den_batch_text = 'it'

        self.treeView_batch.header().hide() 
        self.treeView_samples.header().hide() 
        self.treeView_scans.header().hide() 
        self.treeView_samples_loop.header().hide() 
        self.treeView_samples_loop_scans.header().hide() 


        self.push_create_sample.clicked.connect(self.create_new_sample_func)
        self.push_get_sample.clicked.connect(self.get_sample_pos)
        self.model_samples = QtGui.QStandardItemModel(self)
        self.treeView_samples.setModel(self.model_samples)

        self.push_add_sample.clicked.connect(self.add_new_sample_func)
        self.push_delete_sample.clicked.connect(self.delete_current_sample)
        self.model_batch = QtGui.QStandardItemModel(self)
        self.treeView_batch.setModel(self.model_batch)

        self.push_add_sample_loop.clicked.connect(self.add_new_sample_loop_func)
        self.push_delete_sample_loop.clicked.connect(self.delete_current_samples_loop)
        self.model_samples_loop = QtGui.QStandardItemModel(self)
        self.treeView_samples_loop.setModel(self.model_samples_loop)

        self.push_delete_sample_loop_scan.clicked.connect(self.delete_current_samples_loop_scans)
        self.model_samples_loop_scans = QtGui.QStandardItemModel(self)
        self.treeView_samples_loop_scans.setModel(self.model_samples_loop_scans)

        self.push_create_scan.clicked.connect(self.create_new_scan_func)
        self.push_delete_scan.clicked.connect(self.delete_current_scan)
        self.push_add_scan.clicked.connect(self.add_new_scan_func)
        self.model_scans = QtGui.QStandardItemModel(self)
        self.treeView_scans.setModel(self.model_scans)

        self.push_batch_run.clicked.connect(self.start_batch)
        self.push_batch_print_steps.clicked.connect(self.print_batch)
        self.push_batch_delete.clicked.connect(self.delete_current_batch)

        self.plan_funcs.append(self.prepare_bl)
        self.plan_funcs_names.append(self.prepare_bl.__name__)
        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_scans.currentIndexChanged.connect(self.populateParams_batch)
        self.push_create_scan_update.clicked.connect(self.update_batch_traj)
        self.params1_batch = []
        self.params2_batch = []
        self.params3_batch = []
        if len(self.plan_funcs) != 0:
            self.populateParams_batch(0)

        self.comboBox_sample_loop_motor.addItems(self.mot_sorted_list)
        self.comboBox_sample_loop_motor.currentTextChanged.connect(self.update_loop_values)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.restore_add_loop)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.comboBox_sample_loop_motor.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_start.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_stop.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_step.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.radioButton_sample_rel.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.radioButton_sample_abs.setDisabled)
        self.radioButton_sample_rel.toggled.connect(self.set_loop_values)
        self.last_lut = 0

        self.push_load_csv.clicked.connect(self.load_csv)
        self.push_save_csv.clicked.connect(self.save_csv)



        # Redirect terminal output to GUI
        #sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
        #sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

    def update_combo_edge(self, index):
        self.comboBoxEdge.clear()
        edges = [key for key in list(self.json_data[index].keys()) if key != 'name' and key != 'symbol']
        edges.sort()
        self.comboBoxEdge.addItems(edges)

    def update_e0_value(self, index):
        if self.comboBoxEdge.count() > 0:
            self.edit_E0.setText(str(self.json_data[self.comboBoxElement.currentIndex()][self.comboBoxEdge.currentText()]))

    def enable_fb(self, value):
        if value == 0:
            if self.piezo_thread.go != 0 or self.fb_master != 0 or self.hhm.fb_status.value != 0:
                self.toggle_piezo_fb(0)
        else:
            if self.fb_master == -1:
                return
            self.fb_master = 1
            self.toggle_piezo_fb(2)

    def toggle_piezo_fb(self, value):
        if value == 0:
            self.piezo_thread.go = 0
            self.hhm.fb_status.put(0)
            self.fb_master = 0
            self.checkBox_piezo_fb.setChecked(False)
        else:
            if self.fb_master:
                self.piezo_thread.start()
                self.hhm.fb_status.put(1)
                self.fb_master = -1
            else:
                self.fb_master = -1
                self.checkBox_piezo_fb.setChecked(True)

    def update_fb_status(self, pvname=None, value=None, char_value=None, **kwargs):
        if value:
            value = 2
        self.toggle_piezo_fb(value)

    def update_piezo_params(self):
        self.piezo_line = int(self.hhm.fb_line.value)
        self.piezo_center = float(self.hhm.fb_center.value)
        self.piezo_nlines = int(self.hhm.fb_nlines.value)
        self.piezo_nmeasures = int(self.hhm.fb_nmeasures.value)
        self.piezo_kp = float(self.hhm.fb_pcoeff.value)
        dlg = UpdatePiezoDialog.UpdatePiezoDialog(str(self.piezo_line), str(self.piezo_center), str(self.piezo_nlines), str(self.piezo_nmeasures), str(self.piezo_kp), parent = self)
        if dlg.exec_():
            piezo_line, piezo_center, piezo_nlines, piezo_nmeasures, piezo_kp = dlg.getValues()
            self.piezo_line = int(round(float(piezo_line)))
            self.piezo_center = float(piezo_center)
            self.piezo_nlines = int(round(float(piezo_nlines)))
            self.piezo_nmeasures = int(round(float(piezo_nmeasures)))
            self.piezo_kp = float(piezo_kp)
            self.hhm.fb_line.put(self.piezo_line)
            self.hhm.fb_center.put(self.piezo_center)
            self.hhm.fb_nlines.put(self.piezo_nlines)
            self.hhm.fb_nmeasures.put(self.piezo_nmeasures)
            self.hhm.fb_pcoeff.put(self.piezo_kp)

    def update_piezo_center(self):
        nmeasures = self.piezo_nmeasures
        if nmeasures == 0:
            nmeasures = 1
        self.piezo_thread.adjust_center_point(line = self.piezo_line, center_point = self.piezo_center, n_lines = self.piezo_nlines, n_measures = nmeasures)

    def prepare_bl(self, energy:int = -1):
            energy = int(energy)
            if energy < 0:
                curr_energy = self.hhm.energy.read()['hhm_energy']['value']
            else:
                curr_energy = energy

            print('[Prepare BL] Setting up the beamline to {} eV'.format(curr_energy))


            curr_range = [ran for ran in self.beamline_prep if ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy]
            if not len(curr_range):
                print('Current energy is not valid. :( Aborted.')
                return

            curr_range = curr_range[0]
            pv_he = EpicsSignal(curr_range['pvs']['IC Gas He']['RB PV'], write_pv = curr_range['pvs']['IC Gas He']['PV'])
            print('[Prepare BL] HE {}'.format(curr_range['pvs']['IC Gas He']['value']))
            pv_he.put(curr_range['pvs']['IC Gas He']['value'], wait = True)

            pv_n2 = EpicsSignal(curr_range['pvs']['IC Gas N2']['RB PV'], write_pv = curr_range['pvs']['IC Gas N2']['PV'])
            print('[Prepare BL] N2 {}'.format(curr_range['pvs']['IC Gas He']['value']))
            pv_n2.put(curr_range['pvs']['IC Gas N2']['value'], wait = True)

            # If you go from less than 1000 V to more than 1400 V, you need a delay. 2 minutes
            # For now if you increase the voltage (any values), we will have the delay. 2 minutes

            pv_i0_volt = EpicsSignal(curr_range['pvs']['I0 Voltage']['RB PV'], write_pv = curr_range['pvs']['I0 Voltage']['PV'])
            old_i0 = abs(pv_i0_volt.value)
            print('[Prepare BL] Old I0 Voltage: {} | New I0 Voltage: {}'.format(old_i0, curr_range['pvs']['I0 Voltage']['value']))

            pv_it_volt = EpicsSignal(curr_range['pvs']['It Voltage']['RB PV'], write_pv = curr_range['pvs']['It Voltage']['PV'])
            old_it = abs(pv_it_volt.value)
            print('[Prepare BL] Old It Voltage: {} | New It Voltage: {}'.format(old_it, curr_range['pvs']['It Voltage']['value']))

            pv_ir_volt = EpicsSignal(curr_range['pvs']['Ir Voltage']['RB PV'], write_pv = curr_range['pvs']['Ir Voltage']['PV'])
            old_ir = abs(pv_ir_volt.value)
            print('[Prepare BL] Old Ir Voltage: {} | New Ir Voltage: {}'.format(old_ir, curr_range['pvs']['Ir Voltage']['value']))

            #if (curr_range['pvs']['I0 Voltage']['value'] > 1400 and old_i0 < 1000) or \
            #   (curr_range['pvs']['It Voltage']['value'] > 1400 and old_it < 1000) or \
            #   (curr_range['pvs']['Ir Voltage']['value'] > 1400 and old_ir < 1000):
            if curr_range['pvs']['I0 Voltage']['value'] - old_i0 > 2 or \
               curr_range['pvs']['It Voltage']['value'] - old_it > 2  or \
               curr_range['pvs']['Ir Voltage']['value'] - old_ir > 2 :
                old_time = ttime.time()
                wait_time = 120
                print('[Prepare BL] Waiting for gas ({}s)...'.format(wait_time))
                percentage = 0
                while ttime.time() - old_time < wait_time: # 120 seconds
                    if ttime.time() - old_time >= percentage * wait_time:
                        print('[Prepare BL] {:3}% ({:.1f}s)'.format(int(np.round(percentage * 100)), percentage * wait_time))
                        percentage += 0.1
                    QtWidgets.QApplication.processEvents()
                    ttime.sleep(0.1)
                print('[Prepare BL] 100% ({:.1f}s)'.format(wait_time))
                print('[Prepare BL] Done waiting for gas...')

            pv_i0_volt.put(curr_range['pvs']['I0 Voltage']['value'], wait = True)
            pv_it_volt.put(curr_range['pvs']['It Voltage']['value'], wait = True)
            pv_ir_volt.put(curr_range['pvs']['Ir Voltage']['value'], wait = True)



            #check if CM will move
            close_shutter = 0
            cm = [bpm for bpm in curr_range['pvs']['BPMs'] if bpm['Name'] == 'CM'][0]
            new_cm_value = cm['value']
            if new_cm_value == 'OUT':
                pv = EpicsSignal(cm['OUT RB PV'], write_pv=cm['OUT PV'])
            elif new_cm_value == 'IN':
                pv = EpicsSignal(cm['IN RB PV'], write_pv=cm['IN PV'])
            ttime.sleep(0.1)
            if pv.value == 0:
                close_shutter = 1
            #check if FB will move
            mv_fb = 0
            fb_value = self.fb_positions[curr_range['pvs']['Filterbox Pos']['value'] - 1]
            pv_fb_motor = EpicsMotor(curr_range['pvs']['Filterbox Pos']['PV'], name='pv_fb_motor')
            ttime.sleep(0.1)
            curr_fb_value = pv_fb_motor.read()['pv_fb_motor']['value']
            if abs(fb_value - curr_fb_value) > 20 * (10 ** (-pv_fb_motor.precision)):
                close_shutter = 1
                mv_fb = 1


            def handler(signum, frame):
                print("[Prepare BL] Could not close shutter")
                raise Exception("Timeout")

            if close_shutter:
                signal.signal(signal.SIGALRM, handler)
                signal.alarm(6)
                for shutter in [self.fe_shutters[index] for index, fe_shutter in enumerate(self.fe_shutters) if self.fe_shutters[index].state.read()['{}_state'.format(self.fe_shutters[index].name)]['value'] != 1]:
                    try:
                        shutter.close()
                    except Exception as exc: 
                        print('[Prepare BL] Timeout! Could not close the shutter. Aborting! (Try once again, maybe?)')
                        return

                    tries = 3
                    while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                        QtWidgets.QApplication.processEvents()
                        ttime.sleep(0.1)
                        if tries:
                            shutter.close()
                            tries -= 1
                signal.alarm(0)

            pv_fb_motor = EpicsMotor(curr_range['pvs']['Filterbox Pos']['PV'])
            ttime.sleep(0.1)
            fb_value = self.fb_positions[curr_range['pvs']['Filterbox Pos']['value'] - 1]
            fb_sts_pv = EpicsSignal(curr_range['pvs']['Filterbox Pos']['STS PVS'][curr_range['pvs']['Filterbox Pos']['value'] - 1])
            if mv_fb:
                pv_fb_motor.move(fb_value, wait=False) 

            pv_hhrm_hor = EpicsMotor(curr_range['pvs']['HHRM Hor Trans']['PV'])
            ttime.sleep(0.1)
            pv_hhrm_hor.move(curr_range['pvs']['HHRM Hor Trans']['value'], wait=False)

            bpm_pvs = []
            for bpm in curr_range['pvs']['BPMs']:
                if bpm['value'] == 'IN':
                    pv = EpicsSignal(bpm['IN RB PV'], write_pv=bpm['IN PV'])
                elif bpm['value'] == 'OUT':
                    pv = EpicsSignal(bpm['OUT RB PV'], write_pv=bpm['OUT PV'])
                try:
                    if pv:
                        for i in range(3):
                            pv.put(1)
                            ttime.sleep(0.1)
                        bpm_pvs.append(pv)
                except Exception as exp:
                    print(exp)

            ttime.sleep(0.1)
            while abs(pv_n2.value - curr_range['pvs']['IC Gas N2']['value']) > pv_n2.tolerance * 3 or \
                  abs(pv_he.value - curr_range['pvs']['IC Gas He']['value']) > pv_he.tolerance * 3 or \
                  abs(pv_i0_volt.value) - abs(curr_range['pvs']['I0 Voltage']['value']) > pv_i0_volt.tolerance * 100 or \
                  abs(pv_it_volt.value) - abs(curr_range['pvs']['It Voltage']['value']) > pv_it_volt.tolerance * 100 or \
                  abs(pv_ir_volt.value) - abs(curr_range['pvs']['Ir Voltage']['value']) > pv_ir_volt.tolerance * 100 or \
                  fb_sts_pv.value != 1 or \
                  abs(pv_hhrm_hor.position - curr_range['pvs']['HHRM Hor Trans']['value']) > 3 * (10 ** (-pv_hhrm_hor.precision)) or \
                  len([pv for pv in bpm_pvs if pv.value != 1]):
                QtCore.QCoreApplication.processEvents()

            if close_shutter:
                signal.alarm(6)
                for shutter in [self.fe_shutters[index] for index, fe_shutter in enumerate(self.fe_shutters) if self.fe_shutters[index].state.read()['{}_state'.format(self.fe_shutters[index].name)]['value'] != 0]:
                    try:
                        shutter.open()
                    except Exception as exc: 
                        print('[Prepare BL] Timeout! Could not open the shutter. Aborting! (Try once again, maybe?)')
                        return

                    tries = 3
                    while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
                        QtWidgets.QApplication.processEvents()
                        ttime.sleep(0.1)
                        if tries:
                            shutter.open()
                            tries -= 1
                signal.alarm(0)

            print('[Prepare BL] Beamline preparation done!')

    def prepare_bl_dialog(self):
        curr_energy = self.hhm.energy.read()['hhm_energy']['value']

        curr_range = [ran for ran in self.beamline_prep if ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy]
        if not len(curr_range):
            print('Current energy is not valid. :( Aborted.')
            return

        dlg = Prepare_BL_Dialog.PrepareBLDialog(curr_energy, self.json_blprep, parent = self)
        if dlg.exec_():
            self.prepare_bl()
            

    def update_user(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.label_6.text(), self.label_7.text(), self.label_8.text(), self.label_9.text(), self.label_10.text(), parent = self)
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

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if 'obj' in kwargs.keys():
            if hasattr(kwargs['obj'].parent, 'button'):
                self.current_button = kwargs['obj'].parent.button 

                if int(value) == 0:
                    self.current_button_color = 'lime'
                elif int(value) == 1:
                    self.current_button_color = 'red'
                    
                self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)

    def update_progress(self, pvname = None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        self.progressBar.setValue(int(np.round(self.progressValue)))

    def getX(self, event):
        self.edit_E0_2.setText(str(int(np.round(event.xdata))))

    def getX_gen_scan(self, event):
        if event.button == 2:
            if self.canvas_gen_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position = event.xdata, motor = self.canvas_gen_scan.motor, parent = self.canvas_gen_scan)
                if dlg.exec_():
                    pass

    def save_e0_processing_value(self, string):
        self.settings.setValue('e0_processing', string)

    def selectFile(self):
        if self.checkBox_process_bin.checkState() > 0:
            self.selected_filename_bin = QtWidgets.QFileDialog.getOpenFileNames(directory = '/GPFS/xf08id/User Data/', filter = '*.txt', parent = self)[0]
        else:
            self.selected_filename_bin = [QtWidgets.QFileDialog.getOpenFileName(directory = '/GPFS/xf08id/User Data/', filter = '*.txt', parent = self)[0]]
        if len(self.selected_filename_bin[0]):
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
        self.gen_parser.data_manager.export_dat(filename)
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
        if self.edge_found != int(self.edit_E0_2.text()):
            self.edge_found = -1
        process_thread.finished.connect(self.reset_processing_tab)
        self.active_threads += 1
        self.total_threads += 1
        self.progressBar_processing.setValue(int(np.round(100 * (self.total_threads - self.active_threads)/self.total_threads)))
        process_thread.start()
        print('[Finished Launching Threads]')

    def replot_bin_equal(self):
        # Erase final plot (in case there is old data there)
        self.figure_old_scans_3.ax.clear()
        self.canvas_old_scans_3.draw_idle()

        self.figure_old_scans.ax.clear()
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_3.ax.clear()
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
        if len(np.where(np.diff(np.sign(self.gen_parser.interp_arrays[self.last_den_text][:, 1])))[0]):
            self.den_offset = self.gen_parser.interp_arrays[self.last_den_text][:, 1].max() + 0.2
            print('invalid value encountered in denominator: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(self.den_offset))
            
        result = self.gen_parser.interp_arrays[self.last_num_text][:, 1] / (self.gen_parser.interp_arrays[self.last_den_text][:, 1] - self.den_offset)
        ylabel = '{} / {}'.format(self.last_num_text, self.last_den_text)

        self.bin_offset = 0
        if self.checkBox_log.checkState() > 0:
            ylabel = 'log({})'.format(ylabel)
            warnings.filterwarnings('error')
            try:
                result_log = np.log(result)
            except Warning as wrn:
                self.bin_offset = 0.1 + np.abs(result.min())
                print('{}: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(wrn, self.bin_offset))
                result_log = np.log(result + self.bin_offset)
                #self.checkBox_log.setChecked(False)
            warnings.filterwarnings('default')
            result = result_log
    
        self.figure_old_scans_3.ax.plot(self.gen_parser.interp_arrays[energy_string][:, 1], result, 'b')
        self.figure_old_scans_3.ax.set_ylabel(ylabel)
        self.figure_old_scans_3.ax.set_xlabel(energy_string)


        self.figure_old_scans_2.ax.clear()
        self.figure_old_scans_2.ax2.clear()
        self.canvas_old_scans_2.draw_idle()
        self.toolbar_old_scans_2._views.clear()
        self.toolbar_old_scans_2._positions.clear()
        self.toolbar_old_scans_2._update_view()


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

        if self.checkBox_find_edge.checkState() > 0:
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
        print('[Finished Launching Threads]')


    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        cursor = self.textEdit_terminal.textCursor()
        cursor.movePosition(QtWidgets.QTextCursor.End)
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
            self.addParamControl(list(signature.parameters)[i], default, signature.parameters[list(signature.parameters)[i]].annotation, grid = self.gridLayout_13, params = [self.params1, self.params2, self.params3])
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)


    def addParamControl(self, name, default, annotation, grid, params):
        rows = int((grid.count())/3)
        param1 = QtWidgets.QLabel(str(rows + 1))

        param2 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtWidgets.QSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtWidgets.QDoubleSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtWidgets.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        elif annotation == str:
            param2 = QtWidgets.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        if param2 is not None:
            param3 = QtWidgets.QLabel(default)
            grid.addWidget(param1, rows, 0, QtCore.Qt.AlignTop)
            grid.addWidget(param2, rows, 1, QtCore.Qt.AlignTop)
            grid.addWidget(param3, rows, 2, QtCore.Qt.AlignTop)
            params[0].append(param1)
            params[1].append(param2)
            params[2].append(param3)

    def get_traj_names(self):
        self.label_56.setText(QtWidgets.QFileDialog.getOpenFileName(directory = self.trajectory_path, filter = '*.txt', parent = self)[0].rsplit('/',1)[1])
        self.push_plot_traj.setEnabled(True)

    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax = self.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw_idle()

        self.figure_single_trajectory = Figure()
        self.figure_single_trajectory.set_facecolor(color='#FcF9F6')
        self.canvas_single_trajectory = FigureCanvas(self.figure_single_trajectory)
        self.figure_single_trajectory.ax = self.figure_single_trajectory.add_subplot(111)
        self.figure_single_trajectory.ax2 = self.figure_single_trajectory.ax.twinx()
        self.toolbar_single_trajectory = NavigationToolbar(self.canvas_single_trajectory, self.tab_2, coordinates=True)
        self.toolbar_single_trajectory.setMaximumHeight(25)
        self.plot_single_trajectory.addWidget(self.toolbar_single_trajectory)
        self.plot_single_trajectory.addWidget(self.canvas_single_trajectory)
        self.canvas_single_trajectory.draw_idle()

        self.figure_full_trajectory = Figure()
        self.figure_full_trajectory.set_facecolor(color='#FcF9F6')
        self.canvas_full_trajectory = FigureCanvas(self.figure_full_trajectory)
        self.figure_full_trajectory.add_subplot(111)
        self.figure_full_trajectory.ax = self.figure_full_trajectory.add_subplot(111)
        self.toolbar_full_trajectory = NavigationToolbar(self.canvas_full_trajectory, self.tab_2, coordinates=True)
        self.toolbar_full_trajectory.setMaximumHeight(25)
        self.plot_full_trajectory.addWidget(self.toolbar_full_trajectory)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.canvas_full_trajectory.draw_idle()

        self.figure_tune = Figure()
        self.figure_tune.set_facecolor(color='#FcF9F6')
        self.canvas_tune = FigureCanvas(self.figure_tune)
        self.figure_tune.ax = self.figure_tune.add_subplot(111)
        self.toolbar_tune = NavigationToolbar(self.canvas_tune, self.tab_2, coordinates=True)
        self.plot_tune.addWidget(self.toolbar_tune)
        self.plot_tune.addWidget(self.canvas_tune)
        self.canvas_tune.draw_idle()
        self.cursor_tune = Cursor(self.figure_tune.ax, useblit=True, color='green', linewidth=0.75 )

        self.figure_gen_scan = Figure()
        self.figure_gen_scan.set_facecolor(color='#FcF9F6')
        self.canvas_gen_scan = FigureCanvas(self.figure_gen_scan)
        self.canvas_gen_scan.motor = ''
        self.figure_gen_scan.ax = self.figure_gen_scan.add_subplot(111)
        self.toolbar_gen_scan = NavigationToolbar(self.canvas_gen_scan, self.tab_2, coordinates=True)
        self.plot_gen_scan.addWidget(self.toolbar_gen_scan)
        self.plot_gen_scan.addWidget(self.canvas_gen_scan)
        self.canvas_gen_scan.draw_idle()
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75 )

        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='#FcF9F6')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.figure_gain_matching.add_subplot(111)
        self.toolbar_gain_matching = NavigationToolbar(self.canvas_gain_matching, self.tab_2, coordinates=True)
        self.plot_gen_scan.addWidget(self.toolbar_gain_matching)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw_idle()

        self.figure_old_scans = Figure()
        self.figure_old_scans.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans = FigureCanvas(self.figure_old_scans)
        self.figure_old_scans.ax = self.figure_old_scans.add_subplot(111)
        self.toolbar_old_scans = NavigationToolbar(self.canvas_old_scans, self.tab_2, coordinates=True)
        self.plot_old_scans.addWidget(self.toolbar_old_scans)
        self.plot_old_scans.addWidget(self.canvas_old_scans)
        self.canvas_old_scans.draw_idle()

        self.figure_old_scans_2 = Figure()
        self.figure_old_scans_2.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans_2 = FigureCanvas(self.figure_old_scans_2)
        self.figure_old_scans_2.ax = self.figure_old_scans_2.add_subplot(111)
        self.figure_old_scans_2.ax2 = self.figure_old_scans_2.ax.twinx()
        self.toolbar_old_scans_2 = NavigationToolbar(self.canvas_old_scans_2, self.tab_2, coordinates=True)
        self.plot_old_scans_2.addWidget(self.toolbar_old_scans_2)
        self.plot_old_scans_2.addWidget(self.canvas_old_scans_2)
        self.canvas_old_scans_2.draw_idle()

        self.figure_old_scans_3 = Figure()
        self.figure_old_scans_3.set_facecolor(color='#FcF9F6')
        self.canvas_old_scans_3 = FigureCanvas(self.figure_old_scans_3)
        self.figure_old_scans_3.ax = self.figure_old_scans_3.add_subplot(111)
        self.toolbar_old_scans_3 = NavigationToolbar(self.canvas_old_scans_3, self.tab_3, coordinates=True)
        self.plot_old_scans_3.addWidget(self.toolbar_old_scans_3)
        self.plot_old_scans_3.addWidget(self.canvas_old_scans_3)
        self.canvas_old_scans_3.draw_idle()

        self.figure_batch_waterfall = Figure()
        self.figure_batch_waterfall.set_facecolor(color='#FcF9F6')
        self.canvas_batch_waterfall = FigureCanvas(self.figure_batch_waterfall)
        self.canvas_batch_waterfall.motor = ''
        self.figure_batch_waterfall.ax = self.figure_batch_waterfall.add_subplot(111)
        self.toolbar_batch_waterfall = NavigationToolbar(self.canvas_batch_waterfall, self.tab_2, coordinates=True)
        self.plot_batch_waterfall.addWidget(self.toolbar_batch_waterfall)
        self.plot_batch_waterfall.addWidget(self.canvas_batch_waterfall)
        self.canvas_batch_waterfall.draw_idle()
        self.cursor_batch_waterfall = Cursor(self.figure_batch_waterfall.ax, useblit=True, color='green', linewidth=0.75 )

        self.figure_batch_average = Figure()
        self.figure_batch_average.set_facecolor(color='#FcF9F6')
        self.canvas_batch_average = FigureCanvas(self.figure_batch_average)
        self.canvas_batch_average.motor = ''
        self.figure_batch_average.ax = self.figure_batch_average.add_subplot(111)
        self.toolbar_batch_average = NavigationToolbar(self.canvas_batch_average, self.tab_2, coordinates=True)
        self.plot_batch_average.addWidget(self.toolbar_batch_average)
        self.plot_batch_average.addWidget(self.canvas_batch_average)
        self.canvas_batch_average.draw_idle()
        self.cursor_batch_average = Cursor(self.figure_batch_average.ax, useblit=True, color='green', linewidth=0.75 )



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
        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type != 'SP']:
            if shutter.state.value:
                ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print ('Aborted!')
                    return False
                break

        self.figure_tune.ax.clear()
        self.toolbar_tune._views.clear()
        self.toolbar_tune._positions.clear()
        self.toolbar_tune._update_view()
        self.canvas_tune.draw_idle()
        self.tune_funcs[self.comboBox_4.currentIndex()](float(self.edit_tune_range.text()), float(self.edit_tune_step.text()), self.spinBox_tune_retries.value(), ax = self.figure_tune.ax)


    def run_gen_scan(self):
        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type != 'SP']:
            if shutter.state.value:
                ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print ('Aborted!')
                    return False
                break

        curr_det = ''
        curr_mot = ''
        
        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)

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

        self.figure_gen_scan.ax.clear()
        self.toolbar_gen_scan._views.clear()
        self.toolbar_gen_scan._positions.clear()
        self.toolbar_gen_scan._update_view()
        self.canvas_gen_scan.draw_idle()
        self.canvas_gen_scan.motor = curr_mot
        self.gen_scan_func(curr_det, self.comboBox_gen_detsig.currentText(), curr_mot, rel_start, rel_stop, num_steps, ax = self.figure_gen_scan.ax)
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

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
        self.traj_creator.define(edge_energy = E0, offsets = ([preedge_lo,preedge_hi,edge_hi,postedge_hi]),velocities = ([velocity_preedge, velocity_edge, velocity_postedge]),\
                        stitching = ([preedge_stitch_lo, preedge_stitch_hi, edge_stitch_lo, edge_stitch_hi, postedge_stitch_lo, postedge_stitch_hi]),\
                        servocycle = 16000, padding_lo = padding_preedge ,padding_hi=padding_postedge, sine_duration = sine_duration, 
                        dsine_preedge_duration = dsine_preedge_duration, dsine_postedge_duration = dsine_postedge_duration, trajectory_type = traj_type)
        self.traj_creator.interpolate()

        #Revert trajectory if checkbox checked
        if self.checkBox_traj_revert.isChecked() and self.checkBox_traj_revert.isEnabled():
            self.traj_creator.revert()

        #Plot single trajectory motion
        self.figure_single_trajectory.ax.clear()
        self.figure_single_trajectory.ax2.clear()
        self.toolbar_single_trajectory._views.clear()
        self.toolbar_single_trajectory._positions.clear()
        self.toolbar_single_trajectory._update_view()
        self.figure_single_trajectory.ax.plot(self.traj_creator.time, self.traj_creator.energy, 'ro')
        self.figure_single_trajectory.ax.plot(self.traj_creator.time_grid, self.traj_creator.energy_grid, 'b')
        self.figure_single_trajectory.ax.set_xlabel('Time /s')
        self.figure_single_trajectory.ax.set_ylabel('Energy /eV')
        self.figure_single_trajectory.ax2.plot(self.traj_creator.time_grid[0:-1], self.traj_creator.energy_grid_der, 'r')
        self.canvas_single_trajectory.draw_idle()

        # Tile trajectory
        self.figure_full_trajectory.ax.clear()
        self.toolbar_full_trajectory._views.clear()
        self.toolbar_full_trajectory._positions.clear()
        self.toolbar_full_trajectory._update_view()
        self.canvas_full_trajectory.draw_idle()
        self.traj_creator.tile(reps=self.spinBox_tiling_repetitions.value(), single_direction = self.checkBox_traj_single_dir.isChecked())

        # Convert to encoder counts
        self.traj_creator.e2encoder(float(self.label_angle_offset.text()))
        
        # Draw
        self.figure_full_trajectory.ax.plot(self.traj_creator.encoder_grid, 'b')
        self.figure_full_trajectory.ax.set_xlabel('Servo event / 1/16000 s')
        self.figure_full_trajectory.ax.set_ylabel('Encoder count')
        self.canvas_full_trajectory.draw_idle()

        self.push_save_trajectory.setEnabled(True)


    def save_trajectory(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save trajectory...', self.trajectory_path, '*.txt')[0]
        if filename[-4:] != '.txt' and len(filename):
            filename += '-{}.txt'.format(self.edit_E0.text())
            if (os.path.isfile(filename)): 
                ret = self.questionMessage('Save trajectory...', '{} already exists. Do you want to replace it?'.format(filename.rsplit('/',1)[1]))
                if not ret:
                    print ('Aborted!')
                    return
        elif not len(filename):
            print('\nInvalid name! Select a valid name...')
            return
        else:
            filename = '{}-{}.txt'.format(filename[:-4], self.edit_E0.text())

        if(len(self.traj_creator.energy_grid)):
            if (os.path.isfile(filename)): 
                ret = self.questionMessage('Save trajectory...', '{} already exists. Do you want to replace it?'.format(filename.rsplit('/',1)[1]))
                if not ret:
                    print ('Aborted!')
                    return
            print('Filename = {}'.format(filename))
            np.savetxt(filename, 
	               self.traj_creator.encoder_grid, fmt='%d')
            call(['chmod', '666', filename])
            #self.get_traj_names()
            self.label_56.setText(filename.rsplit('/',1)[1])
            self.push_plot_traj.setEnabled(True)
            print('Trajectory saved! [{}]'.format(filename))
        else:
            print('\nCreate the trajectory first...')

    def plot_traj_file(self):
        self.traj_creator.load_trajectory_file('/GPFS/xf08id/trajectory/' + self.label_56.text())#self.comboBox.currentText())

        self.figure_single_trajectory.ax.clear()
        self.figure_single_trajectory.ax2.clear()
        self.toolbar_single_trajectory._views.clear()
        self.toolbar_single_trajectory._positions.clear()
        self.toolbar_single_trajectory._update_view()
        self.figure_full_trajectory.ax.clear()
        self.toolbar_full_trajectory._views.clear()
        self.toolbar_full_trajectory._positions.clear()
        self.toolbar_full_trajectory._update_view()
        self.canvas_single_trajectory.draw_idle()
        self.canvas_full_trajectory.draw_idle()

        self.figure_full_trajectory.ax.plot(np.arange(0, len(self.traj_creator.energy_grid_loaded)/16000, 1/16000), self.traj_creator.energy_grid_loaded, 'b')
        self.figure_full_trajectory.ax.set_xlabel('Time /s')
        self.figure_full_trajectory.ax.set_ylabel('Energy /eV')
        self.figure_full_trajectory.ax.set_title(self.label_56.text())#self.comboBox.currentText())
        self.canvas_full_trajectory.draw_idle()
        print('Trajectory Load: Done')

        self.push_save_trajectory.setDisabled(True)

    def load_trajectory(self):
        self.traj_manager.load(orig_file_name = self.label_56.text(), new_file_path = self.comboBox_2.currentText())
        self.update_batch_traj()

    def init_trajectory(self):
        self.run_start.setDisabled(True)
        self.traj_manager.init(int(self.comboBox_3.currentText()))
        self.run_start.setEnabled(True)

    def read_trajectory_info(self):
        self.traj_manager.read_info()

    def update_repetitions_spinbox(self):
        if self.checkBox_traj_single_dir.isChecked():
            self.spinBox_tiling_repetitions.setValue(1)
            self.spinBox_tiling_repetitions.setEnabled(0)
        else:
            self.spinBox_tiling_repetitions.setEnabled(1)
            

    def run_scan(self):
        if self.run_type.currentText() == 'get_offsets':
            for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'PH' and self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 1]:
                shutter.close()
                while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                    QtWidgets.QApplication.processEvents()
                    ttime.sleep(0.1)

        else:
            for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type != 'SP']:
                if shutter.state.value:
                    ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')
                    if not ret:
                        print ('Aborted!')
                        return False
                    break

        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
        
        for adc in self.adc_list:
            adc.averaging_points.put(str(value))

        for enc in self.enc_list:
            enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        if self.xia.input_trigger is not None:
            self.xia.input_trigger.unit_sel.put(1) # ms, not us
            self.xia.input_trigger.period_sp.put(int(self.lineEdit_xia_samp.text()))

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
            self.figure.ax.clear()
            self.toolbar._views.clear()
            self.toolbar._positions.clear()
            self.toolbar._update_view()
            self.canvas.draw_idle()

            # Run the scan using the dict created before
            self.current_uid_list = self.plan_funcs[self.run_type.currentIndex()](**run_params, ax=self.figure.ax)

            if self.plan_funcs[self.run_type.currentIndex()].__name__ == 'get_offsets':
                return

            if type(self.current_uid_list) != list:
                self.current_uid_list = [self.current_uid_list]

            filepaths = []
            for i in range(len(self.current_uid_list)):
                try:
                    self.current_uid = self.current_uid_list[i]
                    if self.current_uid == '':
                        self.current_uid = self.db[-1]['start']['uid']

                    if 'xia_filename' in self.db[self.current_uid]['start']:
                            # Parse xia
                            xia_filename = self.db[self.current_uid]['start']['xia_filename']
                            xia_filepath = 'smb://elistavitski-ni/epics/{}'.format(xia_filename)
                            xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                            smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                            try:
                                smbclient.copy()
                            except Exception as exc:
                                if exc.args[1] == 'No such file or directory':
                                    print('*** File not found in the XIA! Check if the hard drive is full! ***')
                                else:
                                    print(exc)
                                print('Abort current scan processing!\nDone!')
                                continue


                    self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                            '{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                            self.db[self.current_uid]['start']['cycle'],
                                                            self.db[self.current_uid]['start']['PROPOSAL'],
                                                            self.db[self.current_uid]['start']['comment'])
                    if os.path.isfile(self.current_filepath):
                        iterator = 2
                        while True:
                            self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                                    '{}-{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                                       self.db[self.current_uid]['start']['cycle'],
                                                                       self.db[self.current_uid]['start']['PROPOSAL'],
                                                                       self.db[self.current_uid]['start']['comment'],
                                                                       iterator)
                            if not os.path.isfile(self.current_filepath):
                                break
                            iterator += 1
                        
                    

                    filepaths.append(self.current_filepath)
                    self.gen_parser.load(self.current_uid)

                    key_base = 'i0'
                    if 'xia_filename' in self.db[self.current_uid]['start']:
                        key_base = 'xia_trigger'
                    self.gen_parser.interpolate(key_base = key_base)

                    self.figure.ax.clear()
                    self.toolbar._views.clear()
                    self.toolbar._positions.clear()
                    self.toolbar._update_view()
                    self.canvas.draw_idle()

                    division = self.gen_parser.interp_arrays['i0'][:, 1] / self.gen_parser.interp_arrays['it'][:, 1]
                    division[division < 0] = 1
                    self.figure.ax.plot(self.gen_parser.interp_arrays['energy'][:, 1], np.log(division))
                    self.figure.ax.set_xlabel('Energy (eV)')
                    self.figure.ax.set_ylabel('log(i0 / it)')

                    # self.gen_parser should be able to generate the interpolated file
                
                    if 'xia_filename' in self.db[self.current_uid]['start']:
                        # Parse xia
                        xia_parser = self.xia_parser
                        xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                        xia_parsed_filepath = self.current_filepath[0 : self.current_filepath.rfind('/') + 1]
                        xia_parser.export_files(dest_filepath = xia_parsed_filepath, all_in_one = True)

                        try:
                            if xia_parser.channelsCount():
                                length = min(xia_parser.pixelsCount(0), len(self.gen_parser.interp_arrays['energy']))
                                if xia_parser.pixelsCount(0) != len(self.gen_parser.interp_arrays['energy']):
                                    raise Exception("XIA Pixels number ({}) != Pizzabox Trigger file ({})".format(xia_parser.pixelsCount(0), len(self.gen_parser.interp_arrays['energy'])))
                            else:
                                raise Exception("Could not find channels data in the XIA file")
                        except Exception as exc:
                            print('***', exc, '***')

                        mcas = []
                        if 'xia_rois' in self.db[self.current_uid]['start']:
                            xia_rois = self.db[self.current_uid]['start']['xia_rois']
                            if 'xia_max_energy' in self.db[self.current_uid]['start']:
                                xia_max_energy = self.db[self.current_uid]['start']['xia_max_energy']
                            else:
                                xia_max_energy = 20
                            
                            self.figure.ax.clear()
                            self.toolbar._views.clear()
                            self.toolbar._positions.clear()
                            self.toolbar._update_view()
                            for mca_number in range(1, xia_parser.channelsCount() + 1):
                                if 'xia1_mca{}_roi0_high'.format(mca_number) in xia_rois:
                                    aux = 'xia1_mca{}_roi'.format(mca_number)#\d{1}.*'
                                    regex = re.compile(aux + '\d{1}.*')
                                    matches = [string for string in xia_rois if re.match(regex, string)]
                                    rois_array = []
                                    for roi_number in range(int(len(matches)/2)):
                                        rois_array.append([xia_rois['xia1_mca{}_roi{}_high'.format(mca_number, roi_number)], xia_rois['xia1_mca{}_roi{}_low'.format(mca_number, roi_number)]])

                                    mcas.append(xia_parser.parse_roi(range(0, length), mca_number, rois_array, xia_max_energy))
                                else:
                                    mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[xia_rois['xia1_mca1_roi0_low'], xia_rois['xia1_mca1_roi0_high']]], xia_max_energy))
                                    
                        else:
                            for mca_number in range(1, xia_parser.channelsCount() + 1):
                                mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[6.7, 6.9]]))

                        for index_roi, roi in enumerate([[i for i in zip(*mcas)][k] for k in range(int(len(matches)/2))]):
                            xia_sum = [sum(i) for i in zip(*roi)]
                            if len(self.gen_parser.interp_arrays['energy']) > length:
                                xia_sum.extend([xia_sum[-1]] * (len(self.gen_parser.interp_arrays['energy']) - length))
                            self.gen_parser.interp_arrays['XIA_SUM_ROI{}'.format(index_roi)] = np.array([self.gen_parser.interp_arrays['energy'][:, 0], xia_sum]).transpose()
                            self.figure.ax.plot(self.gen_parser.interp_arrays['energy'][:, 1], -(self.gen_parser.interp_arrays['XIA_SUM_ROI{}'.format(index_roi)][:, 1]/self.gen_parser.interp_arrays['i0'][:, 1]))

                        self.figure.ax.set_xlabel('Energy (eV)')
                        self.figure.ax.set_ylabel('XIA ROIs')



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
                        QtWidgets.QMessageBox.warning(self, 'Warning!', warningtxt)
                        #raise

                    self.canvas.draw_idle()

                except Exception as exc:
                    print('Could not finish parsing this scan:\n{}'.format(exc))

            if len(self.current_uid_list) and self.checkBox_auto_process.checkState() > 0 and self.active_threads == 0: # Change to a control
                self.tabWidget.setCurrentIndex(5)
                self.selected_filename_bin = filepaths
                self.label_24.setText(' '.join(filepath[filepath.rfind('/') + 1 : len(filepath)] for filepath in filepaths))
                self.process_bin_equal()

        else:
            print('\nPlease, type a comment about the scan in the field "comment"\nTry again')


    def re_abort(self):
        if self.RE.state != 'idle':
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

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type != 'SP' and self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 0]:
            try:
                shutter.open()
            except Exception as exc: 
                print('Timeout! Aborting!')
                return

            while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
                QtWidgets.QApplication.processEvents()
                ttime.sleep(0.1)

        signal.alarm(0)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'closed']:
            shutter.open()

        for func in self.plan_funcs:
            if func.__name__ == 'get_offsets':
                getoffsets_func = func
                break
        self.current_uid_list = getoffsets_func(10, dummy_read=True)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'open']:
            shutter.close()

        print('Done!')            


    def run_gains_test_scan(self):

        def handler(signum, frame):
            print("Could not open shutters")
            raise Exception("end of time")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(6)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type != 'SP' and self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 0]:
            try:
                shutter.open()
            except Exception as exc: 
                print('Timeout! Aborting!')
                return

            while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
                QtWidgets.QApplication.processEvents()
                ttime.sleep(0.1)
        
        signal.alarm(0)

        current_adc_index = self.comboBox_samp_time.currentIndex()
        current_enc_value = self.lineEdit_samp_time.text()

        info = self.traj_manager.read_info(silent=True)
        current_lut = int(self.hhm.lut_number_rbv.value)

        if 'max' not in info[str(current_lut)] or 'min' not in info[str(current_lut)]:
            raise Exception('Could not find max or min information in the trajectory. Try sending it again to the controller.')

        min_en = int(info[str(current_lut)]['min'])
        max_en = int(info[str(current_lut)]['max'])

        edge_energy = int(round((max_en + min_en) / 2))
        preedge_lo = min_en - edge_energy
        postedge_hi = max_en - edge_energy

        self.traj_creator.define(edge_energy = edge_energy, offsets=[preedge_lo, 0, 0, postedge_hi], sine_duration=2.5, trajectory_type='Sine')
        self.traj_creator.interpolate()
        self.traj_creator.tile(reps=1)
        self.traj_creator.e2encoder(0)#float(self.RE.md['angle_offset']))
        # Don't need the offset since we're getting the data already with the offset

        if not len(self.traj_creator.energy_grid):
            raise Exception('Trajectory creation failed. Try again.')

        #Everything ready, send the new daq sampling times:
        self.comboBox_samp_time.setCurrentIndex(8)
        self.current_enc_value = self.lineEdit_samp_time.setText('0.896')
        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
        for adc in self.adc_list:
            adc.averaging_points.put(str(value))
        for enc in self.enc_list:
            enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        filename = '/GPFS/xf08id/trajectory/gain_aux.txt'
        np.savetxt(filename,
                   self.traj_creator.encoder_grid, fmt='%d')
        call(['chmod', '666', filename])
        #print('Trajectory saved! [{}]'.format(filename))

        self.traj_manager.load(orig_file_name = filename[filename.rfind('/') + 1:], orig_file_path = filename[:filename.rfind('/') + 1], new_file_path = '9', ip = '10.8.2.86')

        ttime.sleep(1)

        self.traj_manager.init(9, ip = '10.8.2.86')

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'closed']:
            shutter.open()

        for func in self.plan_funcs:
            if func.__name__ == 'tscan':
                tscan_func = func
                break
        self.current_uid_list = tscan_func('Check gains')

        for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'open']:
            shutter.close()

        # Send sampling time to the pizzaboxes:
        self.comboBox_samp_time.setCurrentIndex(current_adc_index)
        self.current_enc_value = self.lineEdit_samp_time.setText(current_enc_value)
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
        for adc in self.adc_list:
            adc.averaging_points.put(str(value))
        for enc in self.enc_list:
            enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        run = self.db[-1]
        keys = [run['descriptors'][i]['name'] for i, desc in enumerate(run['descriptors'])]
        regex = re.compile('pba\d{1}.*')
        matches = [string for string in keys if re.match(regex, string)]
        devnames = [run['descriptors'][i]['data_keys'][run['descriptors'][i]['name']]['devname'] for i, desc in enumerate(run['descriptors']) if run['descriptors'][i]['name'] in matches]
        
        print_message = ''
        for index, adc in enumerate(matches):
            data = []
            dd = [_['data'] for _ in self.db.get_events(run, stream_name=adc, fill=True)]
            for chunk in dd:
                data.extend(chunk[adc])
            data = pd.DataFrame(np.array(data)[25:-25,3])[0].apply(lambda x: (x >> 8) - 0x40000 if (x >> 8) > 0x1FFFF else x >> 8) * 7.62939453125e-05
            print('{}:   Max = {}   Min = {}'.format(devnames[index], data.max(), data.min()))

            if data.max() > 0 and data.min() > 0:
                print_message += '{} is always positive. Perhaps it\'s floating.\n'.format(devnames[index])
            elif data.min() > -0.039:
                print_message += 'Increase {} gain by 10^2\n'.format(devnames[index])
            elif data.max() <= -0.039 and data.min() > -0.39:
                print_message += 'Increase {} gain by 10^1\n'.format(devnames[index])
            elif data.max() < 0 and data.min() > -3.9:
                print_message += '{} seems to be configured properly.\n'.format(devnames[index])
            elif data.min() <= -3.9:
                print_message += 'Decrease {} gain by 10^1\n'.format(devnames[index])
            else:
                print_message += '{} got a case that the [bad] programmer wasn\'t expecting. Sorry.\n'.format(devnames[index])

        print('-' * 30)
        if print_message:
            print(print_message[:-1])
        print('-' * 30)

        self.traj_manager.init(current_lut, ip = '10.8.2.86')

        print('**** Check gains finished! ****')
        

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
            ax.clear()
            self.toolbar_gain_matching._views.clear()
            self.toolbar_gain_matching._positions.clear()
            self.toolbar_gain_matching._update_view()

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

    def update_listWidgets(self):#, value_num, value_den):
        index = [index for index, item in enumerate([self.listWidget_numerator.item(index) for index in range(self.listWidget_numerator.count())]) if item.text() == self.last_num_text]
        if len(index):
            self.listWidget_numerator.setCurrentRow(index[0])
        else:
            self.listWidget_numerator.setCurrentRow(0)

        index = [index for index, item in enumerate([self.listWidget_denominator.item(index) for index in range(self.listWidget_denominator.count())]) if item.text() == self.last_den_text]
        if len(index):
            self.listWidget_denominator.setCurrentRow(index[0])
        else:
            self.listWidget_denominator.setCurrentRow(0)

        #if(type(value_num[0]) == int):
        #    if value_num[0] < self.listWidget_numerator.count():
        #        self.listWidget_numerator.setCurrentRow(value_num[0])
        #    else:
        #        self.listWidget_numerator.setCurrentRow(0)
        #else:
        #    self.listWidget_numerator.setCurrentItem(value_num[0])

        #if(type(value_den[0]) == int):
        #    if value_den[0] < self.listWidget_denominator.count():
        #        self.listWidget_denominator.setCurrentRow(value_den[0])
        #    else:
        #        self.listWidget_denominator.setCurrentRow(0)
        #else:
        #    self.listWidget_denominator.setCurrentItem(value_den[0])

        
    def create_lists(self, list_num, list_den):
        self.listWidget_numerator.clear()
        self.listWidget_denominator.clear()
        self.listWidget_numerator.insertItems(0, list_num)
        self.listWidget_denominator.insertItems(0, list_den)


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

    def show_scan_help(self):
        title = self.run_type.currentText()
        message = self.plan_funcs[self.run_type.currentIndex()].__doc__
        QtWidgets.QMessageBox.question(self, 
                                   'Help! - {}'.format(title), 
                                   message, 
                                   QtWidgets.QMessageBox.Ok)

    def reset_processing_tab(self):
        self.active_threads -= 1
        print('[Threads] Number of active threads: {}'.format(self.active_threads))
        self.progressBar_processing.setValue(int(np.round(100 * (self.total_threads - self.active_threads)/self.total_threads)))

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
        if self.edge_found != -1:
            self.edit_E0_2.setText(str(self.edge_found))

        if self.active_threads == 0:
            print('[ #### All Threads Finished #### ]')
            self.total_threads = 0
            #self.progressBar_processing.setValue(int(np.round(100)))
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



# Batch mode functions
    def create_new_sample_func(self):
        self.create_new_sample(self.lineEdit_sample_name.text(), self.doubleSpinBox_sample_x.value(), self.doubleSpinBox_sample_y.value())

    def create_new_sample(self, name, x, y):
        parent = self.model_samples.invisibleRootItem()
        item = QtGui.QStandardItem('{} X:{} Y:{}'.format(name, x, y))
        item.setDropEnabled(False)
        item.item_type = 'sample'
        item.x = x
        item.y = y
        #subitem = QtGui.QStandardItem('X: {}'.format(x))
        #subitem.setEnabled(False)
        #item.appendRow(subitem)
        #subitem = QtGui.QStandardItem('Y: {}'.format(y))
        #subitem.setEnabled(False)
        #item.appendRow(subitem)
        parent.appendRow(item)
        self.treeView_samples.expand(self.model_samples.indexFromItem(item))

    def get_sample_pos(self):
        if 'samplexy_x' not in self.mot_list:
            raise Exception('samplexy_x was not passed to the GUI')
        if 'samplexy_y' not in self.mot_list:
            raise Exception('samplexy_y was not passed to the GUI')

        if not self.motors_list[self.mot_list.index('samplexy_x')].connected or not self.motors_list[self.mot_list.index('samplexy_y')].connected:
            raise Exception('SampleXY stage IOC not connected')

        x_value = self.motors_list[self.mot_list.index('samplexy_x')].read()['samplexy_x']['value']
        y_value = self.motors_list[self.mot_list.index('samplexy_y')].read()['samplexy_y']['value']
        self.doubleSpinBox_sample_x.setValue(x_value)
        self.doubleSpinBox_sample_y.setValue(y_value)

    def add_new_sample_func(self):
        indexes = self.treeView_samples.selectedIndexes()
        for index in indexes:
            item = index.model().itemFromIndex(index)
            self.add_new_sample(item)

    def add_new_sample(self, item):
        parent = self.model_batch.invisibleRootItem()
        new_item = item.clone()
        new_item.item_type = 'sample'
        new_item.x = item.x
        new_item.y = item.y
        new_item.setEditable(False)
        new_item.setDropEnabled(False)
        name = new_item.text()[:new_item.text().find(' X:')]#.split()[0]
        new_item.setText('Move to "{}" X:{} Y:{}'.format(name, item.x, item.y))
        for index in range(item.rowCount()):
            subitem = QtGui.QStandardItem(item.child(index))
            subitem.setEnabled(False)
            subitem.setDropEnabled(False)
            new_item.appendRow(subitem)
        parent.appendRow(new_item)

    def select_all_samples(self):
        if len(self.treeView_samples.selectedIndexes()) < self.model_samples.rowCount():
            self.treeView_samples.selectAll()
        else:
            self.treeView_samples.clearSelection()

    def create_new_scan_func(self):
        self.create_new_scan(self.comboBox_scans.currentText(), self.comboBox_lut.currentText())

    def create_new_scan(self, curr_type, traj):

        run_params = {}
        for i in range(len(self.params1_batch)):
            if (self.param_types_batch[i] == int):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].value()
            elif (self.param_types_batch[i] == float):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].value()
            elif (self.param_types_batch[i] == bool):
                run_params[self.params3_batch[i].text().split('=')[0]] = bool(self.params2_batch[i].checkState())
            elif (self.param_types_batch[i] == str):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].text()
        params = str(run_params)[1:-1].replace(': ', ':').replace(',', '').replace("'", "")


        parent = self.model_scans.invisibleRootItem()
        if self.comboBox_lut.isEnabled():
            item = QtGui.QStandardItem('{} Traj:{} {}'.format(curr_type, traj, params))
        else:
            item = QtGui.QStandardItem('{} {}'.format(curr_type, params))
        item.setDropEnabled(False)
        item.item_type = 'sample'
        parent.appendRow(item)
        self.treeView_samples.expand(self.model_samples.indexFromItem(item))

    def add_new_scan_func(self):
        indexes = self.treeView_scans.selectedIndexes()
        for index in indexes:
            item = index.model().itemFromIndex(index)
            self.add_new_scan(item)

    def add_new_scan(self, item):
        parent = self.model_batch.invisibleRootItem()
        new_item = item.clone()
        new_item.item_type = 'scan'
        new_item.setEditable(False)
        new_item.setDropEnabled(False)
        name = new_item.text().split()[0]
        new_item.setText('Run {}'.format(new_item.text()))
        for index in range(item.rowCount()):
            subitem = QtGui.QStandardItem(item.child(index))
            subitem.setEnabled(False)
            subitem.setDropEnabled(False)
            new_item.appendRow(subitem)
        parent.appendRow(new_item)

    def update_loop_values(self, text):
        for i in range(self.comboBox_sample_loop_motor.count()):
            if text == self.mot_list[i]:
                curr_mot = self.motors_list[i]
        if self.radioButton_sample_rel.isChecked():
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                self.doubleSpinBox_motor_range_start.setValue(-0.5)
                self.doubleSpinBox_motor_range_stop.setValue(0.5)
                self.doubleSpinBox_motor_range_step.setValue(0.25)
                self.push_add_sample_loop.setEnabled(True)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.doubleSpinBox_motor_range_start.setValue(0)
                self.doubleSpinBox_motor_range_stop.setValue(0)
                self.doubleSpinBox_motor_range_step.setValue(0.025)
        else:
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                curr_pos = curr_mot.read()[curr_mot.name]['value']
                self.doubleSpinBox_motor_range_start.setValue(curr_pos - 0.1)
                self.doubleSpinBox_motor_range_stop.setValue(curr_pos + 0.1)
                self.doubleSpinBox_motor_range_step.setValue(0.025)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.doubleSpinBox_motor_range_start.setValue(0)
                self.doubleSpinBox_motor_range_stop.setValue(0)
                self.doubleSpinBox_motor_range_step.setValue(0.025)
        
    def restore_add_loop(self, value):
        if value:
            self.push_add_sample_loop.setEnabled(True)

    def set_loop_values(self, checked):
        if checked:
            self.doubleSpinBox_motor_range_start.setValue(-0.5)
            self.doubleSpinBox_motor_range_stop.setValue(0.5)
            self.doubleSpinBox_motor_range_step.setValue(0.25)
            self.push_add_sample_loop.setEnabled(True)
        else:
            motor_text = self.comboBox_sample_loop_motor.currentText()
            self.update_loop_values(motor_text)
            

    def add_new_sample_loop_func(self):
        model_samples = self.treeView_samples_loop.model()
        data_samples = []
        for row in range(model_samples.rowCount()):
            index = model_samples.index(row, 0)
            data_samples.append(str(model_samples.data(index)))

        model_scans = self.treeView_samples_loop_scans.model()
        data_scans = []
        for row in range(model_scans.rowCount()):
            index = model_scans.index(row, 0)
            data_scans.append(str(model_scans.data(index)))

        self.add_new_sample_loop(data_samples, data_scans)

    def add_new_sample_loop(self, samples, scans):
        parent = self.model_batch.invisibleRootItem()
        new_item = QtGui.QStandardItem('Sample Loop')
        new_item.setEditable(False)

        if self.spinBox_sample_loop_rep.value():
            repetitions_item = QtGui.QStandardItem('Repetitions:{}'.format(self.spinBox_sample_loop_rep.value()))
        else:
            repetitions_item = QtGui.QStandardItem('Motor:{} Start:{} Stop:{} Step:{}'.format(self.comboBox_sample_loop_motor.currentText(),
                                                                                              self.doubleSpinBox_motor_range_start.value(),
                                                                                              self.doubleSpinBox_motor_range_stop.value(),
                                                                                              self.doubleSpinBox_motor_range_step.value()))
        new_item.appendRow(repetitions_item)

        if self.radioButton_sample_loop.isChecked():
            primary = 'Samples'
        else:
            primary = 'Scans' 
        primary_item = QtGui.QStandardItem('Primary:{}'.format(primary))
        new_item.appendRow(primary_item)

        samples_item = QtGui.QStandardItem('Samples')
        samples_item.setDropEnabled(False)
        for index in range(len(samples)):
            subitem = QtGui.QStandardItem(samples[index])
            subitem.setDropEnabled(False)
            samples_item.appendRow(subitem)
        new_item.appendRow(samples_item)

        scans_item = QtGui.QStandardItem('Scans')
        scans_item.setDropEnabled(False)
        for index in range(len(scans)):
            subitem = QtGui.QStandardItem(scans[index])
            subitem.setDropEnabled(False)
            scans_item.appendRow(subitem)
        new_item.appendRow(scans_item)

        parent.appendRow(new_item)
        self.treeView_batch.expand(self.model_batch.indexFromItem(new_item))
        for index in range(new_item.rowCount()):
            self.treeView_batch.expand(new_item.child(index).index())

    def delete_current_sample(self):
        view = self.treeView_samples
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_scan(self):
        view = self.treeView_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_samples_loop(self):
        view = self.treeView_samples_loop
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_samples_loop_scans(self):
        view = self.treeView_samples_loop_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_batch(self):
        view = self.treeView_batch
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_all_batch(self):
        view = self.treeView_samples
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_scans
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_samples_loop
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_samples_loop_scans
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_batch
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())
        

    def populateParams_batch(self, index):
        if self.comboBox_scans.currentText()[: 5] != 'tscan':
            self.comboBox_lut.setEnabled(False)
        else:
            self.comboBox_lut.setEnabled(True)

        for i in range(len(self.params1_batch)):
            self.gridLayout_31.removeWidget(self.params1_batch[i])
            self.gridLayout_31.removeWidget(self.params2_batch[i])
            self.gridLayout_31.removeWidget(self.params3_batch[i])
            self.params1_batch[i].deleteLater()
            self.params2_batch[i].deleteLater()
            self.params3_batch[i].deleteLater()
        self.params1_batch = []
        self.params2_batch = []
        self.params3_batch = []
        self.param_types_batch = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default, signature.parameters[list(signature.parameters)[i]].annotation, grid = self.gridLayout_31, params = [self.params1_batch, self.params2_batch, self.params3_batch])
            self.param_types_batch.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def update_batch_traj(self):
        self.trajectories = self.traj_manager.read_info(silent=True)
        self.comboBox_lut.clear()
        self.comboBox_lut.addItems(['{}-{}'.format(lut, self.trajectories[lut]['name']) for lut in self.trajectories if lut != '9'])
        
    def load_csv(self):
        user_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/'.format(self.RE.md['year'],
                                                                  self.RE.md['cycle'],
                                                                  self.RE.md['PROPOSAL'])
        filename = QtWidgets.QFileDialog.getOpenFileName(caption = 'Select file to load', 
                                                     directory = user_filepath, 
                                                     filter = '*.csv', 
                                                     parent = self)[0]
        if filename:
            batman = BatchManager(self)
            batman.load_csv(filename)

    def save_csv(self):
        user_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/'.format(self.RE.md['year'],
                                                                  self.RE.md['cycle'],
                                                                  self.RE.md['PROPOSAL'])
        filename = QtWidgets.QFileDialog.getSaveFileName(caption = 'Select file to save', 
                                                     directory = user_filepath, 
                                                     filter = '*.csv', 
                                                     parent = self)[0]
        if filename:
            if filename[-4:] != '.csv': 
                filename += '.csv'
            batman = BatchManager(self)
            batman.save_csv(filename)

    def pause_unpause_batch(self):
        if self.batch_running == True:
            self.batch_pause = not self.batch_pause
            if self.batch_pause:
                print('Pausing batch run... It will pause in the next step.')
                self.push_batch_pause.setText('Unpause')
            else:
                print('Unpausing batch run...')
                self.push_batch_pause.setText('Pause')
                self.label_batch_step.setText(self.label_batch_step.text()[9:])

    def abort_batch(self):
        if self.batch_running == True:
            self.batch_abort = True
            self.re_abort()

    def start_batch(self):
        print('[Launching Threads]')
        self.batch_processor = process_batch_thread(self)
        self.batch_processor.finished_processing.connect(self.plot_batches)
        self.batch_processor.start()
        self.listWidget_numerator_batch.clear()
        self.listWidget_denominator_batch.clear()
        self.figure_batch_waterfall.ax.clear()
        self.canvas_batch_waterfall.draw_idle()
        self.figure_batch_average.ax.clear()
        self.canvas_batch_average.draw_idle()
        self.run_batch()
        print('[Finished Launching Threads]')

    def print_batch(self):
        print('\n***** Printing Batch Steps *****')
        self.run_batch(print_only = True)
        print('***** Finished Batch Steps *****')

    def plot_batches(self):
        self.figure_batch_waterfall.ax.clear()
        self.toolbar_batch_waterfall._views.clear()
        self.toolbar_batch_waterfall._positions.clear()
        self.toolbar_batch_waterfall._update_view()
        self.canvas_batch_waterfall.draw_idle()

        self.figure_batch_average.ax.clear()
        self.toolbar_batch_average._views.clear()
        self.toolbar_batch_average._positions.clear()
        self.toolbar_batch_average._update_view()
        self.canvas_batch_average.draw_idle()

        largest_range = 0
        for sample_index, sample in enumerate(self.batch_results):
            for data_index, data_set in enumerate(self.batch_results[sample]['data']):
                if self.listWidget_numerator_batch.count() == 0:
                    self.listWidget_numerator_batch.insertItems(0, list(data_set.keys()))
                    self.listWidget_denominator_batch.insertItems(0, list(data_set.keys()))
                    if len(data_set.keys()):
                        while self.listWidget_numerator_batch.count() == 0 or self.listWidget_denominator_batch.count() == 0:
                            QtCore.QCoreApplication.processEvents()
                    index_num = [index for index, item in enumerate([self.listWidget_numerator_batch.item(index) for index in range(self.listWidget_numerator_batch.count())]) if item.text() == self.last_num_batch_text]
                    if len(index_num):
                        self.listWidget_numerator_batch.setCurrentRow(index_num[0])
                    index_den = [index for index, item in enumerate([self.listWidget_denominator_batch.item(index) for index in range(self.listWidget_denominator_batch.count())]) if item.text() == self.last_den_batch_text]
                    if len(index_den):
                        self.listWidget_denominator_batch.setCurrentRow(index_den[0])

                else:
                    if self.listWidget_numerator_batch.currentRow() != -1:
                        self.last_num_batch_text = self.listWidget_numerator_batch.currentItem().text()
                    if self.listWidget_denominator_batch.currentRow() != -1:
                        self.last_den_batch_text = self.listWidget_denominator_batch.currentItem().text()

                energy_string = 'energy'
                result = data_set[self.last_num_batch_text] / data_set[self.last_den_batch_text]

                if self.checkBox_log_batch.checkState() > 0:
                    result = np.log(result)

                if result.max() - result.min() > largest_range:
                    largest_range = result.max() - result.min()
                

        for sample_index, sample in enumerate(self.batch_results):
            for data_index, data_set in enumerate(self.batch_results[sample]['data']):

                energy_string = 'energy'
                result = data_set[self.last_num_batch_text] / data_set[self.last_den_batch_text]
                data_set_all = self.batch_results[sample]['data_all']
                result_all = data_set_all[self.last_num_batch_text] / data_set_all[self.last_den_batch_text]
                #print('data_set', len(data_set['i0']))

                if self.checkBox_log_batch.checkState() > 0:
                    result = np.log(result)
                    result_all = np.log(result_all)

                distance_multiplier = 1.25

                if data_index == 0:
                    text_y = (sample_index * largest_range * distance_multiplier) + (result.max() + result.min())/2
                    bbox_props = dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=1.3)
                    self.figure_batch_waterfall.ax.text(data_set[energy_string][-1], text_y, sample, size=11, horizontalalignment='right', clip_on=True, bbox=bbox_props)
                    self.figure_batch_average.ax.text(data_set_all[energy_string][-1], text_y, sample, size=11, horizontalalignment='right', clip_on=True, bbox=bbox_props)

                self.figure_batch_waterfall.ax.plot(data_set[energy_string], (sample_index * largest_range * distance_multiplier) + result)
                self.figure_batch_average.ax.plot(data_set_all[energy_string], (sample_index * largest_range * distance_multiplier) + result_all)
        self.canvas_batch_waterfall.draw_idle()
        self.canvas_batch_average.draw_idle()

    def check_pause_abort_batch(self):
        if self.batch_abort:
            print('**** Aborting Batch! ****')
            raise Exception('Abort button pressed by user')
        elif self.batch_pause:
            self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
            while self.batch_pause:
                QtCore.QCoreApplication.processEvents()

    def run_batch(self, print_only = False):
        try:
            self.last_lut = 0
            current_index = 0
            self.current_uid_list = []
            if print_only is False:
                self.batch_running = True
                self.batch_pause = False
                self.batch_abort = False

                # Send sampling time to the pizzaboxes:
                value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
                
                for adc in self.adc_list:
                    adc.averaging_points.put(str(value))

                for enc in self.enc_list:
                    enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

                if self.xia.input_trigger is not None:
                    self.xia.input_trigger.unit_sel.put(1) # ms, not us
                    self.xia.input_trigger.period_sp.put(int(self.lineEdit_xia_samp.text()))

                self.batch_results = {}

            for batch_index in range(self.model_batch.rowCount()):
                index = self.model_batch.index(batch_index, 0)
                text = str(self.model_batch.data(index))
                item = self.model_batch.item(batch_index)
                font = QtGui.QFont()
                font.setWeight(QtGui.QFont.Bold)
                item.setFont(font)
                item.setText(text)

                if text.find('Move to ') == 0:
                    name = text[text.find('"') + 1:text.rfind('"')]
                    item_x = text[text.find('" X:') + 4:text.find(' Y:')]
                    item_y = text[text.find(' Y:') + 3:]
                    print('Move to sample "{}" (X: {}, Y: {})'.format(name, item_x, item_y))
                    ### Uncomment
                    if print_only == False:
                        self.label_batch_step.setText('Move to sample "{}" (X: {}, Y: {})'.format(name, item_x, item_y))
                        self.check_pause_abort_batch()
                        self.motors_list[self.mot_list.index('samplexy_x')].move(item_x, wait = False)
                        self.motors_list[self.mot_list.index('samplexy_y')].move(item_y, wait = False)
                        ttime.sleep(0.2)
                        while(self.motors_list[self.mot_list.index('samplexy_x')].moving or \
                              self.motors_list[self.mot_list.index('samplexy_y')].moving):
                            QtCore.QCoreApplication.processEvents()
                    ### Uncomment

                if text.find('Run ') == 0:
                    scan_type = text.split()[0]

                    scans = collections.OrderedDict({})
                    scans_text = text[text.find(' ') + 1:]#scans_tree.child(scans_index).text()
                    scan_name = scans_text[:scans_text.find(' ')]
                    scans_text = scans_text[scans_text.find(' ') + 1:]

                    i = 2
                    if scan_name in scans:
                        sn = scan_name
                        while sn in scans:
                            sn = '{}-{}'.format(scan_name, i)
                            i += 1
                        scan_name = sn
                    scans[scan_name] = collections.OrderedDict((k.strip(), v.strip()) for k,v in
                                                               (item.split(':') for item in scans_text.split(' ') if len(item) > 1))
                    #print(json.dumps(scans, indent=2))

                    for scan in scans:
                        if 'Traj' in scans[scan]:
                            lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                            traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                            ### Uncomment
                            if self.last_lut != lut:
                                print('Init trajectory {} - {}'.format(lut, traj_name))
                                if print_only == False:
                                    self.label_batch_step.setText('Init trajectory {} - {}'.format(lut, traj_name))
                                    self.check_pause_abort_batch()
                                    self.traj_manager.init(int(lut))
                                self.last_lut = lut
                            print('Prepare trajectory {} - {}'.format(lut, traj_name))
                            if print_only == False:
                                self.label_batch_step.setText('Prepare trajectory {} - {}'.format(lut, traj_name))
                                self.check_pause_abort_batch()
                                self.run_prep_traj()
        
                        if 'comment' in scans[scan]:
                            old_comment = scans[scan]['comment']
                            scans[scan]['comment'] = '{}-{}'.format(scans[scan]['comment'], traj_name[:traj_name.find('.txt')])
        
                        if scan.find('-') != -1:
                            scan_name = scan[:scan.find('-')]
                        else:
                            scan_name = scan

                        ### Uncomment
                        if print_only == False:
                            if 'comment' in scans[scan]:
                                self.label_batch_step.setText('Execute {} - comment: {}'.format(scan_name, scans[scan]['comment']))
                                self.check_pause_abort_batch()
                            else:
                                self.label_batch_step.setText('Execute {}'.format(scan_name))
                                self.check_pause_abort_batch()
                            uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                            if uid:
                                self.uids_to_process.extend(uid)
                        ### Uncomment (previous line)

                        if 'comment' in scans[scan]:
                            print('Execute {} - comment: {}'.format(scan_name, scans[scan]['comment']))
                            scans[scan]['comment'] = old_comment
                        else:
                            print('Execute {}'.format(scan_name))






                if text == 'Sample Loop':
                    print('Running Sample Loop...')

                    repetitions = item.child(0).text()
                    rep_type = repetitions[:repetitions.find(':')]
                    if rep_type == 'Repetitions':
                        repetitions = np.arange(int(repetitions[repetitions.find(':') + 1:]))
                    elif rep_type == 'Motor':
                        repetitions = repetitions.split(' ')
                        #rep_motor = self.motors_list[self.motors_list.index(repetitions[0][repetitions[0].find(':') + 1:])]
                        rep_motor = repetitions[0][repetitions[0].find(':') + 1:]
                        rep_motor = [motor for motor in self.motors_list if motor.name == rep_motor][0]
                        rep_start = float(repetitions[1][repetitions[1].find(':') + 1:])
                        rep_stop = float(repetitions[2][repetitions[2].find(':') + 1:])
                        rep_step = float(repetitions[3][repetitions[3].find(':') + 1:])
                        repetitions = np.arange(rep_start, rep_stop + rep_step, rep_step)

                    primary = item.child(1).text()
                    primary = primary[primary.find(':') + 1:]

                    samples = collections.OrderedDict({})
                    if item.child(2).text() != 'Samples':
                        raise Exception('Where are the samples?')
                    samples_tree = item.child(2)
                    for sample_index in range(samples_tree.rowCount()):
                        sample_text = samples_tree.child(sample_index).text()
                        sample_name = sample_text[:sample_text.find(' X:')]
                        sample_text = sample_text[sample_text.find(' X:') + 1:].split()
                        samples[sample_name] = collections.OrderedDict({sample_text[0][0:sample_text[0].find(':')]:float(sample_text[0][sample_text[0].find(':') + 1:]), sample_text[1][0:sample_text[1].find(':')]:float(sample_text[1][sample_text[1].find(':') + 1:])})

                    scans = collections.OrderedDict({})
                    if item.child(3).text() != 'Scans':
                        raise Exception('Where are the scans?')
                    scans_tree = item.child(3)
                    for scans_index in range(scans_tree.rowCount()):
                        scans_text = scans_tree.child(scans_index).text()
                        scan_name = scans_text[:scans_text.find(' ')]
                        scans_text = scans_text[scans_text.find(' ') + 1:]

                        i = 2
                        if scan_name in scans:
                            sn = scan_name
                            while sn in scans:
                                sn = '{}-{}'.format(scan_name, i)
                                i += 1
                            scan_name = sn
                        scans[scan_name] = collections.OrderedDict((k.strip(), v.strip()) for k,v in
                                                                   (item.split(':') for item in scans_text.split(' ') if len(item) > 1))

                    #print(json.dumps(samples, indent=2))
                    #print(json.dumps(scans, indent=2))

                    print('-' * 40)
                    for step_number, rep in enumerate(repetitions):
                        print('Step #{}'.format(step_number + 1))
                        if rep_type == 'Motor':
                            print('Move {} to {} {}'.format(rep_motor.name, rep, rep_motor.egu)) 
                            ### Uncomment
                            if print_only == False:
                                self.label_batch_step.setText('Move {} to {} {}  |  Loop step number: {}/{}'.format(rep_motor.name, rep, rep_motor.egu, step_number + 1, len(repetitions)))
                                self.check_pause_abort_batch()
                                if hasattr(rep_motor, 'move'):
                                    rep_motor.move(rep)
                                elif hasattr(rep_motor, 'put'):
                                    rep_motor.put(rep)
                            ### Uncomment

                        if primary == 'Samples':
                            for index, sample in enumerate(samples):
                                print('-' * 40)
                                print('Move to sample {} (X: {}, Y: {})'.format(sample, samples[sample]['X'], samples[sample]['Y']))
                                ### Uncomment
                                if print_only == False:
                                    self.label_batch_step.setText('Move to sample {} (X: {}, Y: {}) | Loop step number: {}/{}'.format(sample, samples[sample]['X'], samples[sample]['Y'], step_number + 1, len(repetitions)))
                                    self.check_pause_abort_batch()
                                    self.motors_list[self.mot_list.index('samplexy_x')].move(samples[sample]['X'], wait = False)
                                    self.motors_list[self.mot_list.index('samplexy_y')].move(samples[sample]['Y'], wait = False)
                                    ttime.sleep(0.2)
                                    while(self.motors_list[self.mot_list.index('samplexy_x')].moving or \
                                          self.motors_list[self.mot_list.index('samplexy_y')].moving):
                                        QtCore.QCoreApplication.processEvents()
                                ### Uncomment

                                for scan in scans:
                                    if 'Traj' in scans[scan]:
                                        lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                                        traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                                        ### Uncomment
                                        if self.last_lut != lut:
                                            print('Init trajectory {} - {}'.format(lut, traj_name))
                                            if print_only == False:
                                                self.label_batch_step.setText('Init trajectory {} - {} | Loop step number: {}/{}'.format(lut, traj_name, step_number + 1, len(repetitions)))
                                                self.check_pause_abort_batch()
                                                self.traj_manager.init(int(lut))
                                            self.last_lut = lut
                                        print('Prepare trajectory {} - {}'.format(lut, traj_name))
                                        if print_only == False:
                                            self.label_batch_step.setText('Prepare trajectory {} - {} | Loop step number: {}/{}'.format(lut, traj_name, step_number + 1, len(repetitions)))
                                            self.check_pause_abort_batch()
                                            self.run_prep_traj()
                    
                                    if 'comment' in scans[scan]:
                                        old_comment = scans[scan]['comment']
                                        scans[scan]['comment'] = '{}|{}|{}|{}'.format(scans[scan]['comment'], sample, traj_name[:traj_name.find('.txt')], rep + 1)
                    
                                    if scan.find('-') != -1:
                                        scan_name = scan[:scan.find('-')]
                                    else:
                                        scan_name = scan
                
                                    ### Uncomment
                                    if print_only == False:
                                        if 'comment' in scans[scan]:
                                            self.label_batch_step.setText('Execute {} - comment: {} | Loop step number: {}/{}'.format(scan_name, scans[scan]['comment'], step_number + 1, len(repetitions)))
                                            self.check_pause_abort_batch()
                                        else:
                                            self.label_batch_step.setText('Execute {} | Loop step number: {}'.format(scan_name, step_number + 1))
                                            self.check_pause_abort_batch()
                                        uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                                        if uid:
                                            self.uids_to_process.extend(uid)
                                    ### Uncomment (previous line)
                                    
                                    if 'comment' in scans[scan]:    
                                        print('Execute {} - comment: {}'.format(scan_name, scans[scan]['comment']))
                                        scans[scan]['comment'] = old_comment
                                    else:
                                        print('Execute {}'.format(scan_name))






                        elif primary == 'Scans':    
                            for index_scan, scan in enumerate(scans):
                                for index, sample in enumerate(samples):
                                    print('-' * 40)
                                    print('Move to sample {} (X: {}, Y: {})'.format(sample, samples[sample]['X'], samples[sample]['Y']))
                                    ### Uncomment
                                    if print_only == False:
                                        self.label_batch_step.setText('Move to sample {} (X: {}, Y: {}) | Loop step number: {}/{}'.format(sample, samples[sample]['X'], samples[sample]['Y'], step_number + 1, len(repetitions)))
                                        self.check_pause_abort_batch()
                                        self.motors_list[self.mot_list.index('samplexy_x')].move(samples[sample]['X'], wait = False)
                                        self.motors_list[self.mot_list.index('samplexy_y')].move(samples[sample]['Y'], wait = False)
                                        ttime.sleep(0.2)
                                        while(self.motors_list[self.mot_list.index('samplexy_x')].moving or \
                                              self.motors_list[self.mot_list.index('samplexy_y')].moving):
                                            QtCore.QCoreApplication.processEvents()
                                    ### Uncomment
        
                                    lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                                    traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                                    if self.last_lut != lut:
                                        print('Init trajectory {} - {}'.format(lut, traj_name))
                                        if print_only == False:
                                            self.label_batch_step.setText('Init trajectory {} - {} | Loop step number: {}/{}'.format(lut, traj_name, step_number + 1, len(repetitions)))
                                            self.check_pause_abort_batch()
                                            self.traj_manager.init(int(lut))
                                        self.last_lut = lut
                                    print('Prepare trajectory {} - {}'.format(lut, traj_name))
                                    if print_only == False:
                                        self.label_batch_step.setText('Prepare trajectory {} - {} | Loop step number: {}/{}'.format(lut, traj_name, step_number + 1, len(repetitions)))
                                        self.check_pause_abort_batch()
                                        self.run_prep_traj()
        
                                    old_comment = scans[scan]['comment']
                                    scans[scan]['comment'] = '{}|{}|{}|{}'.format(scans[scan]['comment'], sample, traj_name[:traj_name.find('.txt')], rep + 1)
        
                                    if scan.find('-') != -1:
                                        scan_name = scan[:scan.find('-')]
                                    else:
                                        scan_name = scan
        
                                    print('Execute {} - comment: {}'.format(scan_name, scans[scan]['comment']))
                                    ### Uncomment
                                    if print_only == False:
                                        self.label_batch_step.setText('Execute {} - comment: {} | Loop step number: {}/{}'.format(scan_name, scans[scan]['comment'], step_number + 1, len(repetitions)))
                                        self.check_pause_abort_batch()
                                        uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                                        if uid:
                                            self.uids_to_process.extend(uid)
                                    ### Uncomment (previous line)
                                    scans[scan]['comment'] = old_comment
        
                        print('-' * 40)

                font = QtGui.QFont()
                item.setFont(font)
                item.setText(text)

            if print_only == False:
                self.batch_running = False
                self.batch_processor.go = 0
                self.label_batch_step.setText('Finished (Idle)')

        except Exception as e:
            print(e)
            print('Batch run aborted!')
            font = QtGui.QFont()
            item.setFont(font)
            item.setText(text)
            self.batch_running = False
            self.batch_processor.go = 0
            self.label_batch_step.setText('Aborted! (Idle)')
            return


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




# Process batch thread

def represents_int(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

class process_batch_thread(QThread):
    finished_processing = QtCore.pyqtSignal()

    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui

    def run(self):
        uid_list = []
        filepaths = []

        self.go = 1
        while(self.go or len(self.gui.uids_to_process) > 0):
            if len(self.gui.uids_to_process) > 0:
                try:
                    uid = self.gui.uids_to_process.pop(0)
                    self.gui.current_uid = uid

                    if self.gui.db[uid]['start']['plan_name'] == 'get_offset':
                        print('get_offsets, nothing to process')
                        continue

                    if 'xia_filename' in self.gui.db[self.gui.current_uid]['start']:
                        # Parse xia
                        xia_filename = self.gui.db[self.gui.current_uid]['start']['xia_filename']
                        xia_filepath = 'smb://elistavitski-ni/epics/{}'.format(xia_filename)
                        xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                        smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                        try:
                            smbclient.copy()
                        except Exception as exc:
                            if exc.args[1] == 'No such file or directory':
                                print('*** File not found in the XIA! Check if the hard drive is full! ***')
                            else:
                                print(exc)
                            print('Abort current scan processing!\nDone!')
                            continue
        
                    self.gui.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                            '{}.txt'.format(self.gui.db[self.gui.current_uid]['start']['year'],
                                                            self.gui.db[self.gui.current_uid]['start']['cycle'],
                                                            self.gui.db[self.gui.current_uid]['start']['PROPOSAL'],
                                                            self.gui.db[self.gui.current_uid]['start']['comment'])
                    if os.path.isfile(self.gui.current_filepath):
                        iterator = 2
                        while True:
                            self.gui.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                                    '{}-{}.txt'.format(self.gui.db[self.gui.current_uid]['start']['year'],
                                                                       self.gui.db[self.gui.current_uid]['start']['cycle'],
                                                                       self.gui.db[self.gui.current_uid]['start']['PROPOSAL'],
                                                                       self.gui.db[self.gui.current_uid]['start']['comment'],
                                                                       iterator)
                            if not os.path.isfile(self.gui.current_filepath):
                                break
                            iterator += 1
                        
                    
        
                    print('Processing scan {}'.format(self.gui.current_filepath))
                    filepaths.append(self.gui.current_filepath)
                    self.gui.gen_parser.load(self.gui.current_uid)
        
                    key_base = 'i0'
                    if 'xia_filename' in self.gui.db[self.gui.current_uid]['start']:
                        key_base = 'xia_trigger'
                    self.gui.gen_parser.interpolate(key_base = key_base)
        
                    #self.gui.figure.ax.clear()
                    #self.gui.canvas.draw_idle()
        
                    division = self.gui.gen_parser.interp_arrays['i0'][:, 1] / self.gui.gen_parser.interp_arrays['it'][:, 1]
                    division[division < 0] = 1
                
                    if 'xia_filename' in self.gui.db[self.gui.current_uid]['start']:
                        xia_parser = self.gui.xia_parser
                        xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                        xia_parsed_filepath = self.gui.current_filepath[0 : self.gui.current_filepath.rfind('/') + 1]
                        xia_parser.export_files(dest_filepath = xia_parsed_filepath, all_in_one = True)
        
                        if xia_parser.channelsCount():
                            length = min(xia_parser.pixelsCount(0), len(self.gui.gen_parser.interp_arrays['energy']))
                        else:
                            raise Exception("Could not find channels data in the XIA file")


                        mcas = []
                        if 'xia_rois' in self.gui.db[self.gui.current_uid]['start']:
                            xia_rois = self.gui.db[self.gui.current_uid]['start']['xia_rois']
                            
                            for mca_number in range(1, xia_parser.channelsCount() + 1):
                                if 'xia1_mca{}_roi0_high'.format(mca_number) in xia_rois:
                                    aux = 'xia1_mca{}_roi'.format(mca_number)
                                    regex = re.compile(aux + '\d{1}.*')
                                    matches = [string for string in xia_rois if re.match(regex, string)]
                                    rois_array = []
                                    for roi_number in range(int(len(matches)/2)):
                                        rois_array.append([xia_rois['xia1_mca{}_roi{}_high'.format(mca_number, roi_number)], xia_rois['xia1_mca{}_roi{}_low'.format(mca_number, roi_number)]])

                                    mcas.append(xia_parser.parse_roi(range(0, length), mca_number, rois_array))
                                else:
                                    mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[xia_rois['xia1_mca1_roi0_low'], xia_rois['xia1_mca1_roi0_high']]]))
                                    
                        else:
                            for mca_number in range(1, xia_parser.channelsCount() + 1):
                                mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[6.7, 6.9]]))

                        for index_roi, roi in enumerate([[i for i in zip(*mcas)][k] for k in range(int(len(matches)/2))]):
                            xia_sum = [sum(i) for i in zip(*roi)]
                            if len(self.gui.gen_parser.interp_arrays['energy']) > length:
                                xia_sum.extend([xia_sum[-1]] * (len(self.gui.gen_parser.interp_arrays['energy']) - length))
                            self.gui.gen_parser.interp_arrays['XIA_SUM_ROI{}'.format(index_roi)] = np.array([self.gui.gen_parser.interp_arrays['energy'][:, 0], xia_sum]).transpose()

                            #[sum(i) for i in zip(*roi)]
                            #self.gui.gen_parser.interp_arrays['XIA_SUM_ROI{}'.format(index_roi)] = np.array([self.gui.gen_parser.interp_arrays['energy'][:, 0], [sum(i) for i in zip(*roi)]]).transpose()



                    self.gui.gen_parser.export_trace(self.gui.current_filepath[:-4], '')
                    traj_name = self.gui.db[uid]['start']['trajectory_name']
                    if represents_int(traj_name[traj_name.rfind('-') + 1 : traj_name.rfind('.')]):
                        #bin data
                        e0 = int(traj_name[traj_name.rfind('-') + 1 : traj_name.rfind('.')])
                        edge_start = -30
                        edge_end = 50
                        preedge_spacing = 10
                        xanes_spacing = 0.2
                        exafs_spacing = 0.04

                        binned = self.gui.gen_parser.bin(e0, 
                                                         e0 + edge_start, 
                                                         e0 + edge_end, 
                                                         preedge_spacing, 
                                                         xanes_spacing, 
                                                         exafs_spacing)

                        index1 = self.gui.db[uid]['start']['comment'].find('|') + 1
                        index2 = self.gui.db[uid]['start']['comment'].find('|', index1)
                        sample_name = self.gui.db[uid]['start']['comment'][index1:index2]

                        if sample_name in self.gui.batch_results:
                           # print('#2+')
                           # print(len(binned['i0']))
                            self.gui.batch_results[sample_name]['data'].append(self.gui.gen_parser.data_manager.binned_arrays)
                            for key in self.gui.gen_parser.data_manager.binned_arrays.keys():
                                self.gui.batch_results[sample_name]['orig_all'][key] = np.append(self.gui.batch_results[sample_name]['orig_all'][key], self.gui.gen_parser.data_manager.binned_arrays[key])
                            self.gui.gen_parser.interp_arrays = self.gui.batch_results[sample_name]['orig_all']
                            binned = self.gui.gen_parser.bin(e0, 
                                                             e0 + edge_start, 
                                                             e0 + edge_end, 
                                                             preedge_spacing, 
                                                             xanes_spacing, 
                                                             exafs_spacing)
                            self.gui.batch_results[sample_name]['data_all'] = binned
                            #print(len(binned['i0']))
                            
                        else:
                           # print('#1')
                           # print(len(self.gui.gen_parser.data_manager.binned_arrays['i0']))
                            self.gui.batch_results[sample_name] = {'data':[self.gui.gen_parser.data_manager.binned_arrays]}
                            self.gui.batch_results[sample_name]['orig_all'] = {}
                            for key in self.gui.gen_parser.data_manager.binned_arrays.keys():
                                self.gui.batch_results[sample_name]['orig_all'][key] = np.copy(self.gui.gen_parser.data_manager.binned_arrays[key])
                            self.gui.gen_parser.interp_arrays = self.gui.batch_results[sample_name]['orig_all']
                            binned = self.gui.gen_parser.bin(e0, 
                                                             e0 + edge_start, 
                                                             e0 + edge_end, 
                                                             preedge_spacing, 
                                                             xanes_spacing, 
                                                             exafs_spacing)
                            self.gui.batch_results[sample_name]['data_all'] = binned
                            #print(len(binned['i0']))
                        self.finished_processing.emit()

                    print('Finished processing scan {}'.format(self.gui.current_filepath))

                except Exception as exc:
                    print('Could not finish parsing this scan:\n{}'.format(exc))

            else:
                QtCore.QCoreApplication.processEvents()



# Bin threads:

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

        binned = self.gen_parser.bin(e0, 
                                     e0 + edge_start, 
                                     e0 + edge_end, 
                                     preedge_spacing, 
                                     xanes_spacing, 
                                     exafs_spacing)

        warnings.filterwarnings('error')
        try:
            #print(self.gui.bin_offset)
            result = (binned[self.gui.last_num_text] / (binned[self.gui.last_den_text] - self.gui.den_offset)) + self.gui.bin_offset
        except Warning as wrn:
            print('{}: This is not supposed to happen. If it is plotting properly, ignore this message.'.format(wrn))
            #self.gui.checkBox_log.setChecked(False)
        warnings.filterwarnings('default')

        result_orig = (self.gen_parser.data_manager.data_arrays[self.gui.last_num_text] / self.gen_parser.data_manager.data_arrays[self.gui.last_den_text]) + self.gui.bin_offset
        #result = binned[self.gui.listWidget_numerator.currentItem().text()] / binned[self.gui.listWidget_denominator.currentItem().text()]
        #result_orig = self.gen_parser.data_manager.data_arrays[self.gui.listWidget_numerator.currentItem().text()] / self.gen_parser.data_manager.data_arrays[self.gui.listWidget_denominator.currentItem().text()]
        ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

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
                                                         self.gen_parser.interp_arrays,
                                                         self.gen_parser.data_manager.data_arrays[energy_string],
                                                         result_orig,
                                                         k_power)

        plot_info = [k_data[0], k_data[1], '', 'k', r'$\kappa$ * k ^ {}'.format(k_power), self.gui.figure_old_scans.ax, self.gui.canvas_old_scans]
        self.gui.plotting_list.append(plot_info)

        self.gui.push_replot_exafs.setEnabled(True)
        self.gui.push_save_bin.setEnabled(True)

        if self.gui.checkBox_process_bin.checkState() > 0:
            filename = self.gen_parser.curr_filename_save
            self.gen_parser.data_manager.export_dat(filename)
            print('[Binning Thread {}] File Saved! [{}]'.format(self.index, filename[:-3] + 'dat'))

        print('[Binning Thread {}] Finished'.format(self.index))




class process_bin_thread_equal(QThread):
    update_listWidgets = QtCore.pyqtSignal()#list, list)
    create_lists = QtCore.pyqtSignal(list, list)
    def __init__(self, gui, filename, index = 1):
        QThread.__init__(self)
        self.gui = gui
        self.index = index
        print(filename)
        self.filename = filename
        self.gen_parser = xasdata.XASdataGeneric(gui.db)
        self.gen_parser.curr_filename_save = filename

    def __del__(self):
        self.wait()

    def run(self):
        print('[Binning Equal Thread {}] Starting...'.format(self.index))
        self.gen_parser.loadInterpFile(self.filename)

        ordered_dict = collections.OrderedDict(sorted(self.gen_parser.interp_arrays.items()))
        self.create_lists.emit(list(ordered_dict.keys()), list(ordered_dict.keys()))
        #while(self.gui.listWidget_denominator.count() == 0 or self.gui.listWidget_numerator.count() == 0):
            #print('stuck here')
            #self.gui.app.processEvents()
            #QtCore.QCoreApplication.processEvents()
            #QtWidgets.QApplication.instance().processEvents()
            #ttime.sleep(0.1)
            #self.gui.app.processEvents()
        
        if not (self.gui.last_num_text in ordered_dict.keys() and self.gui.last_den_text in ordered_dict.keys()):
             self.gui.last_num_text = list(ordered_dict.keys())[2]
             self.gui.last_den_text = list(ordered_dict.keys())[3]
        
        #if self.gui.listWidget_numerator.count() > 0 and self.gui.listWidget_denominator.count() > 0:
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
            #while(self.gui.listWidget_denominator.currentRow() == -1 or self.gui.listWidget_numerator.currentRow() == -1):
                #self.gui.app.processEvents()
                #QtCore.QCoreApplication.processEvents()
                #QtWidgets.QApplication.instance().processEvents()
                #ttime.sleep(0.001)

            energy_string = self.gen_parser.get_energy_string()

            self.gui.den_offset = 0
            self.gui.bin_offset = 0
            if len(np.where(np.diff(np.sign(self.gen_parser.interp_arrays[self.gui.last_den_text][:, 1])))[0]):
                self.gui.den_offset = self.gen_parser.interp_arrays[self.gui.last_den_text][:, 1].max() + 0.2
                print('invalid value encountered in denominator: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(self.gui.den_offset))

            result = self.gen_parser.interp_arrays[self.gui.last_num_text][:, 1] / (self.gen_parser.interp_arrays[self.gui.last_den_text][:, 1] - self.gui.den_offset)
            ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

            if self.gui.checkBox_log.checkState() > 0:
                ylabel = 'log({})'.format(ylabel)
                warnings.filterwarnings('error')
                try:
                    result_log = np.log(result)
                except Warning as wrn:
                    self.gui.bin_offset = 0.1 + np.abs(result.min())
                    print('{}: Added an offset of {} so that we can plot the graphs properly (only for data visualization)'.format(wrn, self.gui.bin_offset))
                    result_log = np.log(result + self.gui.bin_offset)
                    #self.gui.checkBox_log.setChecked(False)
                warnings.filterwarnings('default')
                result = result_log
            
            plot_info = [self.gen_parser.interp_arrays[energy_string][:, 1], 
                         result, 
                         'b', 
                         energy_string, 
                         ylabel, 
                         self.gui.figure_old_scans_3.ax, 
                         self.gui.canvas_old_scans_3]
            self.gui.plotting_list.append(plot_info)


            bin_eq = self.gen_parser.bin_equal()

            #result = bin_eq[self.gui.listWidget_numerator.currentItem().text()] / bin_eq[self.gui.listWidget_denominator.currentItem().text()]
            result = bin_eq[self.gui.last_num_text] / bin_eq[self.gui.last_den_text]
            ylabel = '{} / {}'.format(self.gui.last_num_text, self.gui.last_den_text)

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
                self.gui.edge_found = -1
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
                    self.gui.edge_found = str(int(np.round(self.gen_parser.data_manager.en_grid[self.gui.edge_index])))#self.gui.edit_E0_2.setText(str(int(np.round(self.gen_parser.data_manager.en_grid[self.gui.edge_index]))))
            else:
                self.gui.edge_index = -1
                

            result_der = self.gen_parser.data_manager.get_derivative(result)
            plot_info = [bin_eq[energy_string], 
                         result_der, 
                         'r', energy_string, 
                         'Derivative', 
                         self.gui.figure_old_scans_2.ax2, 
                         self.gui.canvas_old_scans_2]
            self.gui.plotting_list.append(plot_info)


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
            print(filename)
            process_thread_equal = process_bin_thread_equal(self.gui, filename, index) 
            #self.gui.connect(process_thread_equal, pyqtSignal("finished()"), self.gui.reset_processing_tab)
            process_thread_equal.update_listWidgets.connect(self.gui.update_listWidgets)
            process_thread_equal.create_lists.connect(self.gui.create_lists)
            process_thread_equal.finished.connect(self.gui.reset_processing_tab)
            process_thread_equal.start()
            self.gui.active_threads += 1
            self.gui.total_threads += 1
            self.gui.edge_found = -1

            self.gui.curr_filename_save = filename
            if self.gui.checkBox_process_bin.checkState() > 0:
                process_thread = process_bin_thread(self.gui, index, process_thread_equal, process_thread_equal.gen_parser) 
                #self.gui.connect(process_thread, pyqtSignal("finished()"), self.gui.reset_processing_tab)
                process_thread.finished.connect(self.gui.reset_processing_tab)
                process_thread.start()
                self.gui.active_threads += 1
                self.gui.total_threads += 1
            index += 1
        self.gui.gen_parser = process_thread_equal.gen_parser


class piezo_fb_thread(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui

        P = 0.004 * self.gui.piezo_kp
        I = 0#0.02
        D = 0#0.01
        self.pid = PID.PID(P, I, D)
        self.sampleTime = 0.00025
        self.pid.setSampleTime(self.sampleTime)
        self.pid.windup_guard = 3
        self.go = 0

    def gauss(self, x, *p):
        A, mu, sigma = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2))

    def gaussian_piezo_feedback(self, line = 420, center_point = 655, n_lines = 1, n_measures = 10):
        image = self.gui.bpm_es.image.read()['bpm_es_image_array_data']['value'].reshape((960,1280))

        #image = image.transpose()
        image = image.astype(np.int16)
        sum_lines = sum(image[:, [i for i in range(line - math.floor(n_lines/2), line + math.ceil(n_lines/2))]].transpose())
        #remove background (do it better later)
        if len(sum_lines) > 0:
            sum_lines = sum_lines - (sum(sum_lines) / len(sum_lines))
        index_max = sum_lines.argmax()
        max_value = sum_lines.max()
        min_value = sum_lines.min()

        if max_value >= 10 and max_value <= n_lines * 100 and ((max_value - min_value) / n_lines) > 5:
            coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
            self.pid.SetPoint = 960 - center_point
            self.pid.update(coeff[1])
            deviation = self.pid.output
            #deviation = -(coeff[1] - center_point)
            piezo_diff = deviation #* 0.0855

            curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
            #print(curr_value, piezo_diff, coeff[1])
            self.gui.hhm.pitch.move(curr_value - piezo_diff)

    def adjust_center_point(self, line = 420, center_point = 655, n_lines = 1, n_measures = 10):
        #getting center:
        centers = []
        for i in range(n_measures):
            image = self.gui.bpm_es.image.read()['bpm_es_image_array_data']['value'].reshape((960,1280))

            image = image.astype(np.int16)
            sum_lines = sum(image[:, [i for i in range(line - math.floor(n_lines/2), line + math.ceil(n_lines/2))]].transpose())
            #remove background (do it better later)
            if len(sum_lines) > 0:
                sum_lines = sum_lines - (sum(sum_lines) / len(sum_lines))

            index_max = sum_lines.argmax()
            max_value = sum_lines.max()
            min_value = sum_lines.min()
            #print('n_lines * 100: {} | max_value: {} | ((max_value - min_value) / n_lines): {}'.format(n_lines, max_value, ((max_value - min_value) / n_lines)))
            if max_value >= 10 and max_value <= n_lines * 100 and ((max_value - min_value) / n_lines) > 5:
                coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
                centers.append(960 - coeff[1])
        #print('Centers: {}'.format(centers))
        #print('Old Center Point: {}'.format(center_point))
        if len(centers) > 0:
            center_point = float(sum(centers) / len(centers))
            self.gui.settings.setValue('piezo_center', center_point)
            self.gui.piezo_center = center_point
            self.gui.hhm.fb_center.put(self.gui.piezo_center)
            #print('New Center Point: {}'.format(center_point))

    def run(self):
        self.go = 1
        #self.adjust_center_point(line = self.gui.piezo_line, center_point = self.gui.piezo_center, n_lines = self.gui.piezo_nlines, n_measures = self.gui.piezo_nmeasures)

        while(self.go):
            if len([self.gui.shutters[shutter] for shutter in self.gui.shutters if self.gui.shutters[shutter].shutter_type != 'SP' and self.gui.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 0]) == 0:
                self.gaussian_piezo_feedback(line = self.gui.piezo_line, center_point = self.gui.piezo_center, n_lines = self.gui.piezo_nlines, n_measures = self.gui.piezo_nmeasures)
                ttime.sleep(self.sampleTime)
            else:
                #self.gui.checkBox_piezo_fb.setChecked(0)
                #self.go = 0
                ttime.sleep(self.sampleTime)






