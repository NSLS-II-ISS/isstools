import inspect
import json
import math
import os
import re
import signal
import sys
import time as ttime

from datetime import datetime
from subprocess import call

import numpy as np
import pandas as pd
import pkg_resources

# import PyQt5
from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from scipy.optimize import curve_fit


from isstools.dialogs import (UpdateUserDialog, UpdatePiezoDialog,
                              UpdateAngleOffset, MoveMotorDialog, Prepare_BL_Dialog)
from isstools.pid import PID
from isstools.xiaparser import xiaparser

from isstools.widgets import widget_general_info, widget_trajectory_manager, widget_processing, widget_batch_mode
ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

#print(type(UiXLiveGeneral))

def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class ScanGui(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs = [],
                 prep_traj_plan=None,
                 RE=None,
                 db=None,
                 accelerator=None,
                 hhm=None,
                 shutters={},
                 det_dict={},
                 motors_dict={},
                 general_scan_func = None, parent=None, *args, **kwargs):

        if 'write_html_log' in kwargs:
            self.html_log_func = kwargs['write_html_log']
            del kwargs['write_html_log']
        else:
            self.html_log_func = None

        if 'ic_amplifiers' in kwargs:
            self.ic_amplifiers = kwargs['ic_amplifiers']
            del kwargs['ic_amplifiers']
        else:
            self.ic_amplifiers = None

        if 'auto_tune_elements' in kwargs:
            self.auto_tune_elements = kwargs['auto_tune_elements']['elements']
            self.auto_tune_pre_elements = kwargs['auto_tune_elements']['pre_elements']
            self.auto_tune_post_elements = kwargs['auto_tune_elements']['post_elements']
            del kwargs['auto_tune_elements']
        else:
            self.auto_tune_elements = None

        if 'prepare_bl' in kwargs:
            self.prepare_bl_plan = kwargs['prepare_bl'][0]
            self.prepare_bl_def = kwargs['prepare_bl'][1]
            del kwargs['prepare_bl']
        else:
            self.prepare_bl_plan = None

        if 'set_gains_offsets' in kwargs:
            self.set_gains_offsets_scan = kwargs['set_gains_offsets']
            del kwargs['set_gains_offsets']
        else:
            self.set_gains_offsets_scan = None

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.det_dict = det_dict
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.dets_with_amp = [det for det in self.det_dict
                             if det.name[:3] == 'pba' and hasattr(det, 'amp')]
        if self.dets_with_amp == []:
            self.push_read_amp_gains.setEnabled(False)
        else:
            self.push_read_amp_gains.clicked.connect(self.read_amp_gains)

        if 'get_offsets' in self.plan_funcs_names:
            self.push_get_offsets.clicked.connect(self.run_get_offsets)
        else:
            self.push_get_offsets.setEnabled(False)

        self.run_type.addItems(self.plan_funcs_names)

        if self.prepare_bl_plan is not None:
            self.plan_funcs.append(self.prepare_bl)
            self.plan_funcs_names.append(self.prepare_bl.__name__)

        self.plan_funcs.append(self.adjust_ic_gains)
        self.plan_funcs_names.append(self.adjust_ic_gains.__name__)
        if self.set_gains_offsets_scan is not None:
            self.plan_funcs.append(self.set_gains_offsets_scan)
            self.plan_funcs_names.append(self.set_gains_offsets_scan.__name__)

        self.motors_dict = motors_dict
        self.mot_list = self.motors_dict.keys()
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()

        # Looking for analog pizzaboxes:
        regex = re.compile('pba\d{1}.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.adc_list = [x for x in self.det_dict if x.name in matches]

        # Looking for encoder pizzaboxes:
        regex = re.compile('pb\d{1}_enc.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.enc_list = [x for x in self.det_dict if x.name in matches]

        # Looking for xias:
        regex = re.compile('xia\d{1}')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.xia_list = [x for x in self.det_dict if x.name in matches]
        if len(self.xia_list):
            self.xia = self.xia_list[0]
        else:
            self.xia = None

        self.addCanvas()

        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, RE, db)
        self.layout_general_info.addWidget(self.widget_general_info)
        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm)
        self.layout_trajectroy_manager.addWidget(self.widget_trajectory_manager)
        self.widget_processing = widget_processing.UIProcessing(hhm, db, det_dict)
        self.layout_processing.addWidget(self.widget_processing)
        self.widget_batch_mode = widget_batch_mode.UIBatchMode(self.plan_funcs, self.motors_dict, hhm,
                                                               RE, db, self.widget_processing.gen_parser,
                                                               self.adc_list, self.enc_list, self.xia,
                                                               self.run_prep_traj, self.parse_scans, self.figure,
                                                               self.create_log_scan)
        self.layout_batch.addWidget(self.widget_batch_mode)

        self.run_start.clicked.connect(self.run_scan)
        self.prep_traj_plan = prep_traj_plan
        if self.prep_traj_plan is None:
            self.push_prepare_trajectory.setEnabled(False)
        self.RE = RE
        self.filepaths = []
        if self.RE is not None:
            # self.RE.last_state = ''
            self.RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)
        else:

            self.push_calibrate.setEnabled(False)
            #self.push_update_user.setEnabled(False)
            self.push_re_abort.setEnabled(False)
            self.run_start.setEnabled(False)
            self.run_check_gains.setEnabled(False)

        self.db = db
        if self.db is None:
            self.run_start.setEnabled(False)
        #self.push_update_user.clicked.connect(self.update_user)

        self.gen_scan_func = general_scan_func



        # Initialize 'Beamline setup' tab
        # Populate analog detectors setup section with adcs:
        self.adc_checkboxes = []
        for index, adc_name in enumerate([adc.dev_name.value for adc in self.adc_list if adc.dev_name.value != adc.name]):
            checkbox = QtWidgets.QCheckBox(adc_name)
            checkbox.setChecked(True)
            self.adc_checkboxes.append(checkbox)
            self.gridLayout_analog_detectors.addWidget(checkbox, int(index / 2), index % 2)

        self.hhm = hhm
        if self.hhm is None:
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Trajectories setup'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run Batch'))
            #next two lines to be moved to Beamline status tab
            self.pushEnableHHMFeedback.setEnabled(False)
            self.update_piezo.setEnabled(False)
        else:
            self.hhm.trajectory_progress.subscribe(self.update_progress)
            self.progress_sig.connect(self.update_progressbar)
            self.progressBar.setValue(0)

        self.fb_master = 0
        self.piezo_line = int(self.hhm.fb_line.value)
        self.piezo_center = float(self.hhm.fb_center.value)
        self.piezo_nlines = int(self.hhm.fb_nlines.value)
        self.piezo_nmeasures = int(self.hhm.fb_nmeasures.value)
        self.piezo_kp = float(self.hhm.fb_pcoeff.value)
        self.hhm.fb_status.subscribe(self.update_fb_status)


        json_data = open(pkg_resources.resource_filename('isstools', 'beamline_preparation.json')).read()
        self.json_blprep = json.loads(json_data)
        self.beamline_prep = self.json_blprep[0]
        self.fb_positions = self.json_blprep[1]['FB Positions']
        # curr_energy = 5500
        # for pv, value in [ran['pvs'] for ran in self.json_blprep[0] if ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy][0].items():


        # Initialize XIA tab
        self.xia_parser = xiaparser.xiaparser()
        self.push_gain_matching.clicked.connect(self.run_gain_matching)
        self.xia_graphs_names = []
        self.xia_graphs_labels = []
        self.xia_handles = []

        if self.xia is None:
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in
                 range(self.tabWidget.count())].index('Silicon Drift Detector setup'))
        else:
            self.xia_channels = [int(mca.split('mca')[1]) for mca in self.xia.read_attrs]
            self.xia_tog_channels = []
            if len(self.xia_channels):
                self.push_gain_matching.setEnabled(True)
                self.push_run_xia_measurement.setEnabled(True)
                self.xia.mca_max_energy.subscribe(self.update_xia_params)
                self.xia.real_time.subscribe(self.update_xia_params)
                self.xia.real_time_rb.subscribe(self.update_xia_params)
                self.edit_xia_acq_time.returnPressed.connect(self.update_xia_acqtime_pv)
                self.edit_xia_energy_range.returnPressed.connect(self.update_xia_energyrange_pv)

                max_en = self.xia.mca_max_energy.value
                energies = np.linspace(0, max_en, 2048)
                # np.floor(energies[getattr(self.xia, "mca{}".format(1)).roi1.low.value] * 1000)/1000

                self.roi_colors = []
                for mult in range(4):
                    self.roi_colors.append((.4 + (.2 * mult), 0, 0))
                    self.roi_colors.append((0, .4 + (.2 * mult), 0))
                    self.roi_colors.append((0, 0, .4 + (.2 * mult)))

                for roi in range(12):
                    low = getattr(self.xia, "mca1.roi{}".format(roi)).low.value
                    high = getattr(self.xia, "mca1.roi{}".format(roi)).high.value
                    if low > 0:
                        getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(
                            np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).low.value] * 1000)))
                    else:
                        getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(low))
                    if high > 0:
                        getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(
                            np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).high.value] * 1000)))
                    else:
                        getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(high))

                    label = getattr(self.xia, "mca1.roi{}".format(roi)).label.value
                    getattr(self, 'edit_roi_name_{}'.format(roi)).setText(label)

                    getattr(self, 'edit_roi_from_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                    getattr(self, 'edit_roi_to_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                    getattr(self, 'edit_roi_name_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)

                self.push_run_xia_measurement.clicked.connect(self.start_xia_spectra)
                self.push_run_xia_measurement.clicked.connect(self.update_xia_rois)
                for channel in self.xia_channels:
                    getattr(self, "checkBox_gm_ch{}".format(channel)).setEnabled(True)
                    getattr(self.xia, "mca{}".format(channel)).array.subscribe(self.update_xia_graph)
                    getattr(self, "checkBox_gm_ch{}".format(channel)).toggled.connect(self.toggle_xia_checkbox)
                self.push_chackall_xia.clicked.connect(self.toggle_xia_all)

        # Initialize 'Beamline Status' tab
        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.push_gen_scan_save.clicked.connect(self.save_gen_scan)
        self.push_prepare_autotune.clicked.connect(self.autotune_function)
        #if self.hhm is not None:
        #    self.hhm.energy.subscribe(self.update_hhm_params)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.det_list = [det.dev_name.value if hasattr(det, 'dev_name') else det.name for det in det_dict.keys()]
        self.det_sorted_list = self.det_list
        self.det_sorted_list.sort()
        self.checkBox_tune.stateChanged.connect(self.spinBox_gen_scan_retries.setEnabled)
        self.comboBox_gen_det.addItems(self.det_sorted_list)
        self.comboBox_gen_det_den.addItem('1')
        self.comboBox_gen_det_den.addItems(self.det_sorted_list)
        self.comboBox_gen_mot.addItems(self.mot_sorted_list)
        self.comboBox_gen_det.currentIndexChanged.connect(self.process_detsig)
        self.comboBox_gen_det_den.currentIndexChanged.connect(self.process_detsig_den)
        self.process_detsig()
        self.process_detsig_den()
        found_bpm = 0
        for i in range(self.comboBox_gen_det.count()):
            if 'bpm_es' == list(self.det_dict.keys())[i].name:
                self.bpm_es = list(self.det_dict.keys())[i]
                found_bpm = 1
                break
        if found_bpm == 0 or self.hhm is None:
            self.pushEnableHHMFeedback.setEnabled(False)
            self.update_piezo.setEnabled(False)
            if self.run_start.isEnabled() == False:
                self.tabWidget.removeTab(
                    [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index(
                        'Run'))
        if len(self.mot_sorted_list) == 0 or len(self.det_sorted_list) == 0 or self.gen_scan_func == None:
            self.push_gen_scan.setEnabled(0)

        if self.auto_tune_elements is not None:
            tune_elements = ' | '.join([element['name'] for element in self.auto_tune_elements])
            self.push_prepare_autotune.setToolTip(
                'Elements: ({})\nIf the parameters are not defined, it will use parameters from General Scans boxes (Scan Range, Step Size and Max Retries)'.format(
                    tune_elements))
        else:
            self.push_prepare_autotune.setEnabled(False)

        # Initialize persistent values
        self.settings = QSettings('ISS Beamline', 'XLive')
        #self.edit_E0_2.setText(self.settings.value('e0_processing', defaultValue='11470', type=str))
        #self.edit_E0_2.textChanged.connect(self.save_e0_processing_value)
        self.user_dir = self.settings.value('user_dir', defaultValue = '/GPFS/xf08id/User Data/', type = str)

        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        # Initialize 'run' tab
        self.run_check_gains.clicked.connect(self.run_gains_test)
        self.run_check_gains_scan.clicked.connect(self.adjust_ic_gains)
        self.push_re_abort.clicked.connect(self.re_abort)
        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)
        
        if self.prepare_bl_plan is not None:
            self.push_prepare_bl.clicked.connect(self.prepare_bl_dialog)
            self.push_prepare_bl.setEnabled(True)
        else:
            self.push_prepare_bl.setEnabled(False)
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)

        if self.ic_amplifiers is None:
            self.run_check_gains_scan.setEnabled(False)

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
            self.comboBox_samp_time.currentTextChanged.connect(self.widget_batch_mode.setAnalogSampTime)
            self.comboBox_samp_time.setCurrentIndex(self.adc_list[0].averaging_points.value)

        if len(self.enc_list):
            self.lineEdit_samp_time.textChanged.connect(self.widget_batch_mode.setEncSampTime)
            self.lineEdit_samp_time.setText(str(self.enc_list[0].filter_dt.value / 100000))

        if hasattr(self.xia, 'input_trigger'):
            if self.xia.input_trigger is not None:
                self.xia.input_trigger.unit_sel.put(1)  # ms, not us
                self.lineEdit_xia_samp.textChanged.connect(self.widget_batch_mode.setXiaSampTime)
                self.lineEdit_xia_samp.setText(str(self.xia.input_trigger.period_sp.value))

        # Initialize Ophyd elements
        self.shutters_sig.connect(self.change_shutter_color)
        self.shutters = shutters

        self.fe_shutters = [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'FE']
        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type == 'FE']:
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
            # button.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

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

        # Initialize 'Batch Mode' tab




        # Redirect terminal output to GUI
        sys.stdout = EmittingStream()
        sys.stderr = EmittingStream()
        sys.stdout.textWritten.connect(self.normalOutputWritten)
        sys.stderr.textWritten.connect(self.normalOutputWritten)


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
            self.pushEnableHHMFeedback.setChecked(False)
        else:
            if self.fb_master:
                self.piezo_thread.start()
                self.hhm.fb_status.put(1)
                self.fb_master = -1
            else:
                self.fb_master = -1
                self.pushEnableHHMFeedback.setChecked(True)

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
        dlg = UpdatePiezoDialog.UpdatePiezoDialog(str(self.piezo_line), str(self.piezo_center), str(self.piezo_nlines),
                                                  str(self.piezo_nmeasures), str(self.piezo_kp), parent=self)
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
        self.piezo_thread.adjust_center_point(line=self.piezo_line, center_point=self.piezo_center,
                                              n_lines=self.piezo_nlines, n_measures=nmeasures)

    def prepare_bl(self, energy: int = -1):
        self.RE(self.prepare_bl_plan(energy=energy, print_messages=True, debug=False))

    def prepare_bl_dialog(self):
        curr_energy = float(self.edit_pb_energy.text())

        curr_range = [ran for ran in self.prepare_bl_def[0] if
                      ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy]
        if not len(curr_range):
            print('Current energy is not valid. :( Aborted.')
            return

        dlg = Prepare_BL_Dialog.PrepareBLDialog(curr_energy, self.prepare_bl_def, parent=self)
        if dlg.exec_():
            self.prepare_bl(curr_energy)

    #def update_user(self):
    #    dlg = UpdateUserDialog.UpdateUserDialog(self.label_6.text(), self.label_7.text(), self.label_8.text(),
    #                                            self.label_9.text(), self.label_10.text(), parent=self)
    #    if dlg.exec_():
    #        self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'], self.RE.md['SAF'], self.RE.md[
    #            'PI'] = dlg.getValues()
    #        self.label_6.setText('{}'.format(self.RE.md['year']))
    #        self.label_7.setText('{}'.format(self.RE.md['cycle']))
    #        self.label_8.setText('{}'.format(self.RE.md['PROPOSAL']))
    #        self.label_9.setText('{}'.format(self.RE.md['SAF']))
    #        self.label_10.setText('{}'.format(self.RE.md['PI']))

    def read_amp_gains(self):
        adcs = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        if not len(adcs):
            print('[Read Gains] Please select one or more Analog detectors')
            return

        print('[Read Gains] Starting...')

        det_dict_with_amp = [det for det in self.det_dict if hasattr(det, 'dev_name')]
        for detec in adcs:
            amp = [det.amp for det in det_dict_with_amp if det.dev_name.value == detec]
            if len(amp):
                amp = amp[0]
                gain = amp.get_gain()
                if gain[1]:
                    gain[1] = 'High Speed'
                else:
                    gain[1] = 'Low Noise'

                print('[Read Gains] {} amp: {} - {}'.format(amp.par.dev_name.value, gain[0], gain[1]))
        print('[Read Gains] Done!\n')

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


    def update_progress(self, pvname=None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        self.progressBar.setValue(int(np.round(self.progressValue)))

    def getX_gen_scan(self, event):
        if event.button == 3:
            if self.canvas_gen_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_gen_scan.motor,
                                                      parent=self.canvas_gen_scan)
                if dlg.exec_():
                    pass

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        cursor = self.textEdit_terminal.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)

        if text.find('0;3') >= 0:
            text = text.replace('<', '(')
            text = text.replace('>', ')')
            text = text.replace('[0m', '</font>')
            text = text.replace('[0;31m', '<font color=\"Red\">')
            text = text.replace('[0;32m', '<font color=\"Green\">')
            text = text.replace('[0;33m', '<font color=\"Yellow\">')
            text = text.replace('[0;34m', '<font color=\"Blue\">')
            text = text.replace('[0;36m', '<font color=\"Purple\">')
            text = text.replace('\n', '<br />')
            text += '<br />'
            cursor.insertHtml(text)
        elif text.lower().find('abort') >= 0 or text.lower().find('error') >= 0 or text.lower().find('invalid') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.red)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif text.lower().find('starting') >= 0 or text.lower().find('launching') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.blue)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif text.lower().find('complete') >= 0 or text.lower().find('done') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.darkGreen)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        else:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.black)
            fmt.setFontWeight(QtGui.QFont.Normal)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        self.textEdit_terminal.setTextCursor(cursor)
        self.textEdit_terminal.ensureCursorVisible()

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
            self.addParamControl(list(signature.parameters)[i], default,
                                 signature.parameters[list(signature.parameters)[i]].annotation,
                                 grid=self.gridLayout_13, params=[self.params1, self.params2, self.params3])
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def addParamControl(self, name, default, annotation, grid, params):
        rows = int((grid.count()) / 3)
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

        self.figure_gen_scan = Figure()
        self.figure_gen_scan.set_facecolor(color='#FcF9F6')
        self.canvas_gen_scan = FigureCanvas(self.figure_gen_scan)
        self.canvas_gen_scan.motor = ''
        self.figure_gen_scan.ax = self.figure_gen_scan.add_subplot(111)
        self.toolbar_gen_scan = NavigationToolbar(self.canvas_gen_scan, self.tab_2, coordinates=True)
        self.plot_gen_scan.addWidget(self.toolbar_gen_scan)
        self.plot_gen_scan.addWidget(self.canvas_gen_scan)
        self.canvas_gen_scan.draw_idle()
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75)

        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='#FcF9F6')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.figure_gain_matching.add_subplot(111)
        self.toolbar_gain_matching = NavigationToolbar(self.canvas_gain_matching, self.tab_2, coordinates=True)
        self.plot_gain_matching.addWidget(self.toolbar_gain_matching)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw_idle()

        self.figure_xia_all_graphs = Figure()
        self.figure_xia_all_graphs.set_facecolor(color='#FcF9F6')
        self.canvas_xia_all_graphs = FigureCanvas(self.figure_xia_all_graphs)
        self.figure_xia_all_graphs.ax = self.figure_xia_all_graphs.add_subplot(111)
        self.toolbar_xia_all_graphs = NavigationToolbar(self.canvas_xia_all_graphs, self.tab_2, coordinates=True)
        self.plot_xia_all_graphs.addWidget(self.toolbar_xia_all_graphs)
        self.plot_xia_all_graphs.addWidget(self.canvas_xia_all_graphs)
        self.canvas_xia_all_graphs.draw_idle()
        self.cursor_xia_all_graphs = Cursor(self.figure_xia_all_graphs.ax, useblit=True, color='green', linewidth=0.75)
        self.figure_xia_all_graphs.ax.clear()

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
        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type != 'SP']:
            if shutter.state.value:
                ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print('Aborted!')
                    return False
                break

        self.figure_tune.ax.clear()
        self.toolbar_tune._views.clear()
        self.toolbar_tune._positions.clear()
        self.toolbar_tune._update_view()
        self.canvas_tune.draw_idle()

    def save_gen_scan(self):
        run = self.db[self.last_gen_scan_uid]
        self.user_directory = '/GPFS/xf08id/User Data/{}.{}.{}/' \
            .format(run['start']['year'],
                    run['start']['cycle'],
                    run['start']['PROPOSAL'])

        # last_table = self.db.get_table(run)

        detectors_names = []
        for detector in run['start']['plan_args']['detectors']:
            text = detector.split('name=')[1]
            detectors_names.append(text[1: text.find('\'', 1)])

        numerator_name = detectors_names[0]
        denominator_name = ''
        if len(detectors_names) > 1:
            denominator_name = detectors_names[1]

        text = run['start']['plan_args']['motor'].split('name=')[1]
        motor_name = text[1: text.find('\'', 1)]

        numerator_devname = ''
        denominator_devname = ''
        for descriptor in run['descriptors']:
            if 'data_keys' in descriptor:
                if numerator_name in descriptor['data_keys']:
                    numerator_devname = descriptor['data_keys'][numerator_name]['devname']
                if denominator_name in descriptor['data_keys']:
                    denominator_devname = descriptor['data_keys'][denominator_name]['devname']

        ydata = []
        xdata = []
        for line in self.figure_gen_scan.ax.lines:
            ydata.extend(line.get_ydata())
            xdata.extend(line.get_xdata())

        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save scan...', self.user_directory, '*.txt')[0]
        if filename[-4:] != '.txt':
            filename += '.txt'

        start = run['start']

        year = start['year']
        cycle = start['cycle']
        saf = start['SAF']
        pi = start['PI']
        proposal = start['PROPOSAL']
        scan_id = start['scan_id']
        real_uid = start['uid']
        start_time = start['time']
        stop_time = run['stop']['time']

        human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_stop_time = str(datetime.fromtimestamp(stop_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))

        if len(numerator_devname):
            numerator_name = numerator_devname
        result_name = numerator_name
        if len(denominator_name):
            if len(denominator_devname):
                denominator_name = denominator_devname
            result_name += '/{}'.format(denominator_name)

        header = '{}  {}'.format(motor_name, result_name)
        comments = '# Year: {}\n' \
                   '# Cycle: {}\n' \
                   '# SAF: {}\n' \
                   '# PI: {}\n' \
                   '# PROPOSAL: {}\n' \
                   '# Scan ID: {}\n' \
                   '# UID: {}\n' \
                   '# Start time: {}\n' \
                   '# Stop time: {}\n' \
                   '# Total time: {}\n#\n# '.format(year,
                                                    cycle,
                                                    saf,
                                                    pi,
                                                    proposal,
                                                    scan_id,
                                                    real_uid,
                                                    human_start_time,
                                                    human_stop_time,
                                                    human_duration)

        matrix = np.array([xdata, ydata]).transpose()
        matrix = self.gen_parser.data_manager.sort_data(matrix, 0)

        fmt = ' '.join(
            ['%d' if array.dtype == np.dtype('int64') else '%.6f' for array in [np.array(xdata), np.array(ydata)]])

        np.savetxt(filename,
                   np.array([xdata, ydata]).transpose(),
                   delimiter=" ",
                   header=header,
                   fmt=fmt,
                   comments=comments)

    def run_gen_scan(self, **kwargs):
        if 'ignore_shutter' in kwargs:
            ignore_shutter = kwargs['ignore_shutter']
        else:
            ignore_shutter = False

        if 'curr_element' in kwargs:
            curr_element = kwargs['curr_element']
        else:
            curr_element = None

        if 'repeat' in kwargs:
            repeat = kwargs['repeat']
        else:
            repeat = False

        if not ignore_shutter:
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type != 'SP']:
                if shutter.state.value:
                    ret = self.questionMessage('Photon shutter closed', 'Proceed with the shutter closed?')
                    if not ret:
                        print ('Aborted!')
                        return False
                    break

        if curr_element is not None:
            self.comboBox_gen_det.setCurrentText(curr_element['det_name'])
            self.comboBox_gen_detsig.setCurrentText(curr_element['det_sig'])
            self.comboBox_gen_det_den.setCurrentText('1')
            self.comboBox_gen_mot.setCurrentText(curr_element['motor_name'])
            self.edit_gen_range.setText(str(curr_element['scan_range']))
            self.edit_gen_step.setText(str(curr_element['step_size']))
            self.checkBox_tune.setChecked(curr_element['autotune'])
            self.spinBox_gen_scan_retries.setValue(curr_element['retries'])

        curr_det = ''
        curr_mot = ''
        detectors = []

        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)

        for i in range(self.comboBox_gen_det.count()):
            if hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].dev_name.value:
                    curr_det = list(self.det_dict.keys())[i]
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == list(self.det_dict.keys())[i].dev_name.value:
                    curr_det = list(self.det_dict.keys())[i]
                    detectors.append(curr_det)
            else:
                if self.comboBox_gen_det.currentText() == list(self.det_dict.keys())[i].name:
                    curr_det = list(self.det_dict.keys())[i]
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == list(self.det_dict.keys())[i].name:
                    curr_det = list(self.det_dict.keys())[i]
                    detectors.append(curr_det)

        curr_mot = self.motors_dict[self.comboBox_gen_mot.currentText()]['object']

        if curr_det == '':
            print('Detector not found. Aborting...')
            raise

        if curr_mot == '':
            print('Motor not found. Aborting...')
            raise

        rel_start = -float(self.edit_gen_range.text()) / 2
        rel_stop = float(self.edit_gen_range.text()) / 2
        num_steps = int(round(float(self.edit_gen_range.text()) / float(self.edit_gen_step.text()))) + 1

        if not repeat:
            self.figure_gen_scan.ax.clear()
            self.toolbar_gen_scan._views.clear()
            self.toolbar_gen_scan._positions.clear()
            self.toolbar_gen_scan._update_view()
            self.canvas_gen_scan.draw_idle()
            self.canvas_gen_scan.motor = curr_mot

        result_name = self.comboBox_gen_det.currentText()
        if self.comboBox_gen_det_den.currentText() != '1':
            result_name += '/{}'.format(self.comboBox_gen_det_den.currentText())

        self.push_gen_scan.setEnabled(False)
        try:
            uid_list = list(self.gen_scan_func(detectors, self.comboBox_gen_detsig.currentText(), 
                                               self.comboBox_gen_detsig_den.currentText(), 
                                               result_name, curr_mot, rel_start, rel_stop, 
                                               num_steps, self.checkBox_tune.isChecked(), 
                                               retries = self.spinBox_gen_scan_retries.value(), 
                                               ax = self.figure_gen_scan.ax))
        except Exception as exc:
            print('[General Scan] Aborted! Exception: {}'.format(exc))
            print('[General Scan] Limit switch reached . Set narrower range and try again.')
            uid_list = []

        self.figure_gen_scan.tight_layout()
        self.canvas_gen_scan.draw_idle()
        if len(uid_list) and curr_element is None:
            self.create_log_scan(uid_list[0], self.figure_gen_scan)
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        self.push_gen_scan.setEnabled(True)
        self.last_gen_scan_uid = self.db[-1]['start']['uid']
        self.push_gen_scan_save.setEnabled(True)

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

    def process_detsig_den(self):
        self.comboBox_gen_detsig_den.clear()
        for i in range(self.comboBox_gen_det_den.count() - 1):
            if hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det_den.currentText() == list(self.det_dict.keys())[i].dev_name.value:
                    curr_det = list(self.det_dict.keys())[i]
                    detsig = self.det_dict[curr_det]
                    self.comboBox_gen_detsig_den.addItems(detsig)
            else:
                if self.comboBox_gen_det_den.currentText() == list(self.det_dict.keys())[i].name:
                    curr_det = list(self.det_dict.keys())[i]
                    detsig = self.det_dict[curr_det]
                    self.comboBox_gen_detsig_den.addItems(detsig)
        if self.comboBox_gen_det_den.currentText() == '1':
            self.comboBox_gen_detsig_den.addItem('1')
            self.checkBox_tune.setEnabled(True)
        else:
            self.checkBox_tune.setChecked(False)
            self.checkBox_tune.setEnabled(False)

    def autotune_function(self):
        print('[Autotune procedure] Starting...')
        self.pushEnableHHMFeedback.setChecked(False)
        first_run = True

        for pre_element in self.auto_tune_pre_elements:
            if pre_element['read_back'].value != pre_element['value']:
                if hasattr(pre_element['motor'], 'move'):
                    move_function = pre_element['motor'].move
                elif hasattr(pre_element['motor'], 'put'):
                    move_function = pre_element['motor'].put
                for repeat in range(pre_element['tries']):
                    move_function(pre_element['value'])
                    ttime.sleep(0.1)

        for element in self.auto_tune_elements:
            if element['max_retries'] != -1 and element['scan_range'] != -1 and element['step_size'] != -1:
                retries = element['max_retries']
                scan_range = element['scan_range']
                step_size = element['step_size']
            else:
                retries = self.spinBox_gen_scan_retries.value()
                scan_range = float(self.edit_gen_range.text())
                step_size = float(self.edit_gen_step.text())
            curr_element = {'retries': retries, 'scan_range': scan_range, 'step_size': step_size,
                            'det_name': element['detector_name'], 'det_sig': element['detector_signame'],
                            'motor_name': element['name']}
            curr_element['autotune'] = not self.checkBox_autotune_manual.isChecked()

            button = None
            repeat = True
            first_try = True
            while repeat:
                repeat = False
                self.run_gen_scan(curr_element=curr_element, ignore_shutter=not first_run, repeat=not first_try)
                if first_run:
                    first_run = False

                if self.checkBox_autotune_manual.isChecked():
                    self.tune_dialog = QtWidgets.QMessageBox(
                        text='Please, select {} position and click OK or Retry'.format(curr_element['motor_name']),
                        standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Cancel,
                        parent=self)
                    self.tune_dialog.setModal(False)
                    self.tune_dialog.show()
                    while self.tune_dialog.isVisible():
                        QtWidgets.QApplication.processEvents()
                    button = self.tune_dialog.clickedButton()
                    if button.text() == '&Cancel':
                        break
                    elif button.text() == '&OK':
                        self.create_log_scan(self.last_gen_scan_uid, self.figure_gen_scan)
                        continue
                    elif button.text() == 'Retry':
                        repeat = True
                        first_try = False
            if button is not None:
                if button.text() == '&Cancel':
                    break

        for post_element in self.auto_tune_post_elements:
            if post_element['read_back'].value != post_element['value']:
                if hasattr(post_element['motor'], 'move'):
                    move_function = post_element['motor'].move
                elif hasattr(post_element['motor'], 'put'):
                    move_function = post_element['motor'].put
                for repeat in range(post_element['tries']):
                    move_function(post_element['value'])
                    ttime.sleep(0.1)

        print('[Autotune procedure] Complete')


    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())



    def update_repetitions_spinbox(self):
        if self.checkBox_traj_single_dir.isChecked():
            self.spinBox_tiling_repetitions.setValue(1)
            self.spinBox_tiling_repetitions.setEnabled(0)
        else:
            self.spinBox_tiling_repetitions.setEnabled(1)

    def run_scan(self):
        if self.run_type.currentText() == 'get_offsets':
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'PH' and
                                            self.shutters[shutter].state.read()['{}_state'.format(shutter)][
                                                'value'] != 1]:
                shutter.close()
                while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                    QtWidgets.QApplication.processEvents()
                    ttime.sleep(0.1)

        else:
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type != 'SP']:
                if shutter.state.value:
                    ret = self.questionMessage('Shutter closed',
                                               'Would you like to run the scan with the shutter closed?')
                    if not ret:
                        print('Aborted!')
                        return False
                    break

        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))

        for adc in self.adc_list:
            adc.averaging_points.put(str(value))

        for enc in self.enc_list:
            enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        if self.xia.input_trigger is not None:
            self.xia.input_trigger.unit_sel.put(1)  # ms, not us
            self.xia.input_trigger.period_sp.put(int(self.lineEdit_xia_samp.text()))

        self.comment = self.params2[0].text()
        if (self.comment):
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

            self.filepaths = []
            self.current_uid_list = []
            process_after_scan = self.checkBox_parse_after_scan.checkState()

            # Run the scan using the dict created before
            for uid in self.plan_funcs[self.run_type.currentIndex()](**run_params, ax=self.figure.ax):

                if self.plan_funcs[self.run_type.currentIndex()].__name__ == 'get_offsets' or uid == None:
                    return

                self.current_uid_list.append(uid)
                if process_after_scan:
                    self.parse_scans(uid)
                    self.create_log_scan(self.current_uid, self.figure)

            if not process_after_scan:
                for uid in self.current_uid_list:
                    self.parse_scans(uid)
                    self.create_log_scan(self.current_uid, self.figure)

            if self.checkBox_auto_process.checkState() > 0 and self.widget_processing.active_threads == 0:
                self.tabWidget.setCurrentIndex(
                    [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Processing'))
                self.widget_processing.selected_filename_bin = self.filepaths
                self.widget_processing.label_24.setText(
                    ' '.join(filepath[filepath.rfind('/') + 1: len(filepath)] for filepath in self.filepaths))
                self.widget_processing.process_bin_equal()

        else:
            print('\nPlease, type the name of the scan in the field "name"\nTry again')

    def parse_scans(self, uid):
        # Erase last graph
        self.figure.ax.clear()
        self.toolbar._views.clear()
        self.toolbar._positions.clear()
        self.toolbar._update_view()

        year = self.db[uid]['start']['year']
        cycle = self.db[uid]['start']['cycle']
        proposal = self.db[uid]['start']['PROPOSAL']
        # Create dirs if they are not there
        log_path = '/GPFS/xf08id/User Data/'
        if log_path[-1] != '/':
            log_path += '/'
        log_path = '{}{}.{}.{}/'.format(log_path, year, cycle, proposal)
        if (not os.path.exists(log_path)):
            os.makedirs(log_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', log_path])
            call(['chmod', '770', log_path])

        log_path = log_path + 'log/'
        if (not os.path.exists(log_path)):
            os.makedirs(log_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', log_path])
            call(['chmod', '770', log_path])

        snapshots_path = log_path + 'snapshots/'
        if (not os.path.exists(snapshots_path)):
            os.makedirs(snapshots_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', snapshots_path])
            call(['chmod', '770', snapshots_path])

        try:
            self.current_uid = uid
            if self.current_uid == '':
                self.current_uid = self.db[-1]['start']['uid']

            if 'xia_filename' in self.db[self.current_uid]['start']:
                # Parse xia
                xia_filename = self.db[self.current_uid]['start']['xia_filename']
                xia_filepath = 'smb://xf08id-nas1/xia_data/{}'.format(xia_filename)
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
                    return

            self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                    '{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                    self.db[self.current_uid]['start']['cycle'],
                                                    self.db[self.current_uid]['start']['PROPOSAL'],
                                                    self.db[self.current_uid]['start']['name'])
            if os.path.isfile(self.current_filepath):
                iterator = 2
                while True:
                    self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                            '{}-{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                               self.db[self.current_uid]['start']['cycle'],
                                                               self.db[self.current_uid]['start']['PROPOSAL'],
                                                               self.db[self.current_uid]['start']['name'],
                                                               iterator)
                    if not os.path.isfile(self.current_filepath):
                        break
                    iterator += 1

            self.filepaths.append(self.current_filepath)
            self.widget_processing.gen_parser.load(self.current_uid)

            key_base = 'i0'
            if 'xia_filename' in self.db[self.current_uid]['start']:
                key_base = 'xia_trigger'
            self.widget_processing.gen_parser.interpolate(key_base=key_base)

            division = self.widget_processing.gen_parser.interp_arrays['i0'][:, 1] / self.widget_processing.gen_parser.interp_arrays['it'][:, 1]
            division[division < 0] = 1
            self.figure.ax.plot(self.widget_processing.gen_parser.interp_arrays['energy'][:, 1], np.log(division))
            self.figure.ax.set_xlabel('Energy (eV)')
            self.figure.ax.set_ylabel('log(i0 / it)')

            # self.gen_parser should be able to generate the interpolated file

            if 'xia_filename' in self.db[self.current_uid]['start']:
                # Parse xia
                xia_parser = self.xia_parser
                xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                xia_parsed_filepath = self.current_filepath[0: self.current_filepath.rfind('/') + 1]
                xia_parser.export_files(dest_filepath=xia_parsed_filepath, all_in_one=True)

                try:
                    if xia_parser.channelsCount():
                        length = min(xia_parser.pixelsCount(0), len(self.widget_processing.gen_parser.interp_arrays['energy']))
                        if xia_parser.pixelsCount(0) != len(self.widget_processing.gen_parser.interp_arrays['energy']):
                            raise Exception(
                                "XIA Pixels number ({}) != Pizzabox Trigger file ({})".format(xia_parser.pixelsCount(0),
                                                                                              len(
                                                                                                  self.widget_processing.gen_parser.interp_arrays[
                                                                                                      'energy'])))
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
                        if '{}_mca{}_roi0_high'.format(self.xia.name, mca_number) in xia_rois:
                            aux = '{}_mca{}_roi'.format(self.xia.name, mca_number)  # \d{1}.*'
                            regex = re.compile(aux + '\d{1}.*')
                            matches = [string for string in xia_rois if re.match(regex, string)]
                            rois_array = []
                            roi_numbers = [roi_number for roi_number in
                                           [roi.split('mca{}_roi'.format(mca_number))[1].split('_high')[0] for roi in
                                            xia_rois if len(roi.split('mca{}_roi'.format(mca_number))) > 1] if
                                           len(roi_number) <= 3]
                            for roi_number in roi_numbers:
                                rois_array.append(
                                    [xia_rois['{}_mca{}_roi{}_high'.format(self.xia.name, mca_number, roi_number)],
                                     xia_rois['{}_mca{}_roi{}_low'.format(self.xia.name, mca_number, roi_number)]])

                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, rois_array, xia_max_energy))
                        else:
                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [
                                [xia_rois['xia1_mca1_roi0_low'], xia_rois['xia1_mca1_roi0_high']]], xia_max_energy))

                else:
                    for mca_number in range(1, xia_parser.channelsCount() + 1):
                        mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[6.7, 6.9]]))

                for index_roi, roi in enumerate([[i for i in zip(*mcas)][ind] for ind, k in enumerate(roi_numbers)]):
                    xia_sum = [sum(i) for i in zip(*roi)]
                    if len(self.widget_processing.gen_parser.interp_arrays['energy']) > length:
                        xia_sum.extend([xia_sum[-1]] * (len(self.widget_processing.gen_parser.interp_arrays['energy']) - length))

                    roi_label = getattr(self, 'edit_roi_name_{}'.format(roi_numbers[index_roi])).text()
                    if not len(roi_label):
                        roi_label = 'XIA_ROI{}'.format(roi_numbers[index_roi])

                    self.widget_processing.gen_parser.interp_arrays[roi_label] = np.array(
                        [self.widget_processing.gen_parser.interp_arrays['energy'][:, 0], xia_sum]).transpose()
                    self.figure.ax.plot(self.widget_processing.gen_parser.interp_arrays['energy'][:, 1], -(
                        self.widget_processing.gen_parser.interp_arrays[roi_label][:, 1] / self.widget_processing.gen_parser.interp_arrays['i0'][:, 1]))

                self.figure.ax.set_xlabel('Energy (eV)')
                self.figure.ax.set_ylabel('XIA ROIs')

            self.widget_processing.gen_parser.export_trace(self.current_filepath[:-4], '')

        except Exception as exc:
            print('Could not finish parsing this scan:\n{}'.format(exc))

    def create_log_scan(self, uid, figure):
        self.canvas.draw_idle()
        if self.html_log_func is not None:
            self.html_log_func(uid, figure)

    def re_abort(self):
        if self.RE.state != 'idle':
            self.RE.abort()
            self.RE.is_aborted = True

    def update_re_state(self):
        palette = self.label_11.palette()
        if (self.RE.state == 'idle'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif (self.RE.state == 'running'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif (self.RE.state == 'paused'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        elif (self.RE.state == 'abort'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_11.setPalette(palette)
        self.label_11.setText(self.RE.state)
        # if self.RE.state != self.RE.last_state:
        #    self.RE.last_state = self.RE.state

    def update_hhm_params(self, value, **kwargs):
        if kwargs['obj'].name == 'hhm_energy':
            text = '{:.2f}'.format(round(value, 2))
            if text != self.last_text:
                self.edit_pb_energy.setText('{:.2f}'.format(round(value, 2)))
                self.last_text = text

    def run_get_offsets(self):
        for shutter in [self.shutters[shutter] for shutter in self.shutters
                        if self.shutters[shutter].shutter_type == 'PH' and 
                        self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 1]:
            shutter.close()
            while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                QtWidgets.QApplication.processEvents()
                ttime.sleep(0.1)
        get_offsets = [func for func in self.plan_funcs if func.__name__ == 'get_offsets'][0]

        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.value in adc_names]

        list(get_offsets(20, *adcs))
        #list(get_offsets())

    def run_gains_test(self):

        def handler(signum, frame):
            print("Could not open shutters")
            raise Exception("Timeout! Aborted!")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(6)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type != 'SP' and
                                        self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 0]:
            try:
                shutter.open()
            except Exception as exc:
                print('Timeout! Aborting!')
                return

            while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
                QtWidgets.QApplication.processEvents()
                ttime.sleep(0.1)

        signal.alarm(0)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'closed']:
            shutter.open()

        for func in self.plan_funcs:
            if func.__name__ == 'get_offsets':
                getoffsets_func = func
                break

        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.value in adc_names]

        self.current_uid_list = list(getoffsets_func(20, *adcs, dummy_read=True))

        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'open']:
            shutter.close()
        print('Done!')            

    def adjust_ic_gains(self, trajectory:int=-1):

        trajectory = int(trajectory)
        if trajectory < 1 or trajectory > 8:
            current_lut = int(self.hhm.lut_number_rbv.value)
        else:
            current_lut = trajectory

        def handler(signum, frame):
            print("Could not open shutters")
            raise Exception("Timeout! Aborted!")

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(6)

        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type != 'SP' and
                        self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 0]:

            try:
                shutter.open()
            except Exception as exc:
                print('Timeout! Aborting!')
                return

        #    while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
        #        QtWidgets.QApplication.processEvents()
        #        ttime.sleep(0.1)

        signal.alarm(0)

        current_adc_index = self.comboBox_samp_time.currentIndex()
        current_enc_value = self.lineEdit_samp_time.text()

        info = self.traj_manager.read_info(silent=True)

        if 'max' not in info[str(current_lut)] or 'min' not in info[str(current_lut)]:
            raise Exception(
                'Could not find max or min information in the trajectory. Try sending it again to the controller.')

        min_en = int(info[str(current_lut)]['min'])
        max_en = int(info[str(current_lut)]['max'])

        edge_energy = int(round((max_en + min_en) / 2))
        preedge_lo = min_en - edge_energy
        postedge_hi = max_en - edge_energy

        self.traj_creator.define(edge_energy=edge_energy, offsets=[preedge_lo, 0, 0, postedge_hi], sine_duration=2.5,
                                 trajectory_type='Sine')
        self.traj_creator.interpolate()
        self.traj_creator.tile(reps=1)
        self.traj_creator.e2encoder(0)  # float(self.RE.md['angle_offset']))
        # Don't need the offset since we're getting the data already with the offset

        if not len(self.traj_creator.energy_grid):
            raise Exception('Trajectory creation failed. Try again.')

        # Everything ready, send the new daq sampling times:
        self.comboBox_samp_time.setCurrentIndex(3)
        self.current_enc_value = self.lineEdit_samp_time.setText('0.028')
        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
        for adc in self.adc_list:
            adc.averaging_points.put(str(value))
        for enc in self.enc_list:
            enc.filter_dt.put(float(self.lineEdit_samp_time.text()) * 100000)

        filename = '/GPFS/xf08id/trajectory/gain_aux.txt'
        np.savetxt(filename,
                   self.traj_creator.energy_grid, fmt='%.6f')
        call(['chmod', '666', filename])

        self.traj_manager.load(orig_file_name=filename[filename.rfind('/') + 1:],
                               orig_file_path=filename[:filename.rfind('/') + 1], new_file_path='9', is_energy=True,
                               offset=float(self.label_angle_offset.text()), ip='10.8.2.86')

        ttime.sleep(1)

        self.traj_manager.init(9, ip='10.8.2.86')

        not_done = 1
        max_tries = 1
        while not_done and max_tries:
            not_done = 0
            max_tries -= 1

            for shutter in [self.shutters[shutter] for shutter in self.shutters if self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'closed']:
                shutter.open()

            for func in self.plan_funcs:
                if func.__name__ == 'tscan':
                    tscan_func = func
                    break
            self.current_uid_list = list(tscan_func('Check gains', ''))

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

            adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]

            run = self.db[-1]
            keys = [run['descriptors'][i]['name'] for i, desc in enumerate(run['descriptors'])]
            regex = re.compile('pba\d{1}.*')
            matches = [string for string in keys if re.match(regex, string)]
            devnames = [run['descriptors'][i]['data_keys'][run['descriptors'][i]['name']]['devname'] 
                        for i, desc in enumerate(run['descriptors']) if run['descriptors'][i]['name'] in matches
                        and run['descriptors'][i]['data_keys'][run['descriptors'][i]['name']]['devname'] in adc_names]
            matches = [run['descriptors'][i]['name'] for i, desc in enumerate(run['descriptors']) if
                       run['descriptors'][i]['name'] in matches and
                       run['descriptors'][i]['data_keys'][run['descriptors'][i]['name']]['devname'] in adc_names]

            print_message = ''
            for index, adc in enumerate(matches):
                data = []
                dd = [_['data'] for _ in self.db.get_events(run, stream_name=adc, fill=True)]
                for chunk in dd:
                    data.extend(chunk[adc])
                data = pd.DataFrame(np.array(data)[25:-25,3])[0].apply(lambda x: (x >> 8) - 0x40000 
                                    if (x >> 8) > 0x1FFFF else x >> 8) * 7.62939453125e-05

                try:
                    if '{}_amp'.format(devnames[index]) in self.ic_amplifiers:
                        curr_amp = self.ic_amplifiers['{}_amp'.format(devnames[index])]
                        saturation = curr_amp.par.dev_saturation.value

                        curr_gain = self.ic_amplifiers['{}_amp'.format(devnames[index])].get_gain()
                        exp = int(curr_gain[0][-1])
                        curr_hs = curr_gain[1]
                        if curr_amp.par.polarity == 'neg':
                            if (data < saturation).sum() < len(data) * 0.01:
                                data[data < saturation] = data.mean()
                            print('{}:   Max = {}   Min = {}'.format(devnames[index], data.max(), data.min()))
                        
                            if data.max() > 0 and data.min() > 0:
                                print_message += '{} is always positive. Perhaps it\'s floating.\n'.format(devnames[index])
                            elif data.min() > saturation/100:
                                exp += 2
                                print_message += 'Increasing {} gain by 10^2. New gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.min() > saturation/10:
                                exp += 1
                                print_message += 'Increasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.max() < 0 and data.min() > saturation:
                                print_message += '{} seems to be configured properly. Current gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.min() <= saturation:
                                exp -= 1
                                print_message += 'Decreasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index], exp)
                            else:
                                print_message += '{} got a case that the [bad] programmer wasn\'t expecting. Sorry.\n'.format(devnames[index])
        
                            if (data.min() > saturation/10 or data.min() < saturation) and not (data.max() > 0 and data.min() > 0):
                                not_done = 1
                                self.ic_amplifiers['{}_amp'.format(devnames[index])].set_gain(exp, high_speed = curr_hs)

                        elif curr_amp.par.polarity == 'pos':
                            if (data > saturation).sum() < len(data) * 0.01:
                                data[data > saturation] = data.mean()
                            print('{}:   Max = {}   Min = {}'.format(devnames[index], data.max(), data.min()))

                            if data.max() < 0 and data.min() < 0:
                                print_message += '{} is always negative. Perhaps it\'s floating.\n'.format(devnames[index])
                            elif data.max() < saturation/100:
                                exp += 2
                                print_message += 'Increasing {} gain by 10^2. New gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.max() < saturation/10:
                                exp += 1
                                print_message += 'Increasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.min() > 0 and data.max() < saturation:
                                print_message += '{} seems to be configured properly. Current gain: 10^{}\n'.format(devnames[index], exp)
                            elif data.max() >= saturation:
                                exp -= 1
                                print_message += 'Decreasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index], exp)
                            else:
                                print_message += '{} got a case that the [bad] programmer wasn\'t expecting. Sorry.\n'.format(devnames[index])

                            if (data.max() < saturation/10 or data.max() > saturation) and not (data.min() < 0 and data.max() < 0):
                                not_done = 1
                                self.ic_amplifiers['{}_amp'.format(devnames[index])].set_gain(exp, high_speed = curr_hs)
                                 
                except Exception as exc:
                    print('Exception: {}'.format(exc))

            print('-' * 30)
            if print_message:
                print(print_message[:-1])
            print('-' * 30)

        self.traj_manager.init(current_lut, ip='10.8.2.86')

        print('[Gain set scan] Complete\n')

    def toggle_xia_checkbox(self, value):
        if value:
            self.xia_tog_channels.append(self.sender().text())
        elif self.sender().text() in self.xia_tog_channels:
            self.xia_tog_channels.remove(self.sender().text())
        self.erase_xia_graph()
        for chan in self.xia_tog_channels:
            self.update_xia_graph(getattr(self.xia, 'mca{}.array.value'.format(chan)),
                                  obj=getattr(self.xia, 'mca{}.array'.format(chan)))

    def toggle_xia_all(self):
        if len(self.xia_tog_channels) != len(self.xia.read_attrs):
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(True)
        else:
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(False)

    def update_xia_params(self, value, **kwargs):
        if kwargs['obj'].name == 'xia1_real_time':
            self.edit_xia_acq_time.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_real_time_rb':
            self.label_acq_time_rbv.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_mca_max_energy':
            self.edit_xia_energy_range.setText('{:.0f}'.format(value * 1000))

    def erase_xia_graph(self):
        self.figure_xia_all_graphs.ax.clear()

        for roi in range(12):
            if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                    self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))

        self.toolbar_xia_all_graphs._views.clear()
        self.toolbar_xia_all_graphs._positions.clear()
        self.toolbar_xia_all_graphs._update_view()
        self.xia_graphs_names.clear()
        self.xia_graphs_labels.clear()
        self.xia_handles.clear()
        self.canvas_xia_all_graphs.draw_idle()

    def start_xia_spectra(self):
        if self.xia.collect_mode.value != 0:
            self.xia.collect_mode.put(0)
            ttime.sleep(2)
        self.xia.erase_start.put(1)

    def update_xia_rois(self):
        energies = np.linspace(0, float(self.edit_xia_energy_range.text()) / 1000, 2048)

        for roi in range(12):
            if float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) < 0 or float(
                    getattr(self, 'edit_roi_to_{}'.format(roi)).text()) < 0:
                exec('start{} = -1'.format(roi))
                exec('end{} = -1'.format(roi))
            else:
                indexes_array = np.where(
                    (energies >= float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) / 1000) & (
                    energies <= float(getattr(self, 'edit_roi_to_{}'.format(roi)).text()) / 1000) == True)[0]
                if len(indexes_array):
                    exec('start{} = indexes_array.min()'.format(roi))
                    exec('end{} = indexes_array.max()'.format(roi))
                else:
                    exec('start{} = -1'.format(roi))
                    exec('end{} = -1'.format(roi))
            exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi, roi,
                                                                                                            roi))
            exec('label{} = self.edit_roi_name_{}.text()'.format(roi, roi))

        for channel in self.xia_channels:
            for roi in range(12):
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).low.put(eval('start{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).high.put(eval('end{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).label.put(eval('label{}'.format(roi)))

        for roi in range(12):
            if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                        roi, roi))
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                        roi, roi))

            else:
                exec('self.figure_xia_all_graphs.ax.roi{}l.set_xdata([roi{}x[0], roi{}x[0]])'.format(roi, roi, roi))
                exec('self.figure_xia_all_graphs.ax.roi{}h.set_xdata([roi{}x[1], roi{}x[1]])'.format(roi, roi, roi))

        self.figure_xia_all_graphs.ax.grid(True)
        self.canvas_xia_all_graphs.draw_idle()

    def update_xia_acqtime_pv(self):
        self.xia.real_time.put(float(self.edit_xia_acq_time.text()))

    def update_xia_energyrange_pv(self):
        self.xia.mca_max_energy.put(float(self.edit_xia_energy_range.text()) / 1000)

    def update_xia_graph(self, value, **kwargs):
        curr_name = kwargs['obj'].name
        curr_index = -1
        if len(self.figure_xia_all_graphs.ax.lines):
            if float(self.edit_xia_energy_range.text()) != self.figure_xia_all_graphs.ax.lines[0].get_xdata()[-1]:
                self.figure_xia_all_graphs.ax.clear()
                for roi in range(12):
                    if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                            self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))

                self.toolbar_xia_all_graphs._views.clear()
                self.toolbar_xia_all_graphs._positions.clear()
                self.toolbar_xia_all_graphs._update_view()
                self.xia_graphs_names.clear()
                self.xia_graphs_labels.clear()
                self.canvas_xia_all_graphs.draw_idle()

        if curr_name in self.xia_graphs_names:
            for index, name in enumerate(self.xia_graphs_names):
                if curr_name == name:
                    curr_index = index
                    line = self.figure_xia_all_graphs.ax.lines[curr_index]
                    line.set_ydata(value)
                    break

        else:
            ch_number = curr_name.split('_')[1].split('mca')[1]
            if ch_number in self.xia_tog_channels:
                self.xia_graphs_names.append(curr_name)
                label = 'Chan {}'.format(ch_number)
                self.xia_graphs_labels.append(label)
                handles, = self.figure_xia_all_graphs.ax.plot(
                    np.linspace(0, float(self.edit_xia_energy_range.text()), 2048), value, label=label)
                self.xia_handles.append(handles)
                self.figure_xia_all_graphs.ax.legend(self.xia_handles, self.xia_graphs_labels)

            if len(self.figure_xia_all_graphs.ax.lines) == len(self.xia_tog_channels) != 0:
                for roi in range(12):
                    exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi,
                                                                                                                    roi,
                                                                                                                    roi))

                for roi in range(12):
                    if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                                roi, roi))
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                                roi, roi))

                self.figure_xia_all_graphs.ax.grid(True)

        self.figure_xia_all_graphs.ax.relim()
        self.figure_xia_all_graphs.ax.autoscale(True, True, True)
        y_interval = self.figure_xia_all_graphs.ax.get_yaxis().get_data_interval()
        if len(y_interval):
            if y_interval[0] != 0 or y_interval[1] != 0:
                self.figure_xia_all_graphs.ax.set_ylim([y_interval[0] - (y_interval[1] - y_interval[0]) * 0.05,
                                                        y_interval[1] + (y_interval[1] - y_interval[0]) * 0.05])
        self.canvas_xia_all_graphs.draw_idle()

    def run_gain_matching(self):
        ax = self.figure_gain_matching.add_subplot(111)
        gain_adjust = [0.001] * len(self.xia_channels)  # , 0.001, 0.001, 0.001]
        diff = [0] * len(self.xia_channels)  # , 0, 0, 0]
        diff_old = [0] * len(self.xia_channels)  # , 0, 0, 0]

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
            for chann in self.xia_channels:
                # If checkbox of current channel is checked:
                if getattr(self, "checkBox_gm_ch{}".format(chann)).checkState() > 0:

                    # Get current channel pre-amp gain:
                    curr_ch_gain = getattr(self.xia, "pre_amp_gain{}".format(chann))

                    coeff = self.xia_parser.gain_matching(self.xia, self.edit_center_gain_matching.text(),
                                                          self.edit_range_gain_matching.text(), chann, ax)
                    # coeff[0] = Intensity
                    # coeff[1] = Fitted mean
                    # coeff[2] = Sigma

                    diff[chann - 1] = float(self.edit_gain_matching_target.text()) - float(coeff[1] * 1000)

                    if i != 0:
                        sign = (diff[chann - 1] * diff_old[chann - 1]) / math.fabs(
                            diff[chann - 1] * diff_old[chann - 1])
                        if int(sign) == -1:
                            gain_adjust[chann - 1] /= 2
                    print('Chan ' + str(chann) + ': ' + str(diff[chann - 1]) + '\n')

                    # Update current channel pre-amp gain:
                    curr_ch_gain.put(curr_ch_gain.value - diff[chann - 1] * gain_adjust[chann - 1])
                    diff_old[chann - 1] = diff[chann - 1]

                    self.canvas_gain_matching.draw_idle()

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
        # self.softspace = sys.__stdout__.softspace
        self.tell = sys.__stdout__.tell
        self.truncate = sys.__stdout__.truncate
        self.writable = sys.__stdout__.writable
        self.writelines = sys.__stdout__.writelines

    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))
        # Comment next line if the output should be printed only in the GUI
        sys.__stdout__.write(text)


class piezo_fb_thread(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui

        P = 0.004 * self.gui.piezo_kp
        I = 0  # 0.02
        D = 0  # 0.01
        self.pid = PID.PID(P, I, D)
        self.sampleTime = 0.00025
        self.pid.setSampleTime(self.sampleTime)
        self.pid.windup_guard = 3
        self.go = 0

    def gauss(self, x, *p):
        A, mu, sigma = p
        return A * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2))

    def gaussian_piezo_feedback(self, line = 420, center_point = 655, n_lines = 1, n_measures = 10):
        # Eli's comment - that's where the check for the intensity should go.
        image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))

        image = image.astype(np.int16)
        sum_lines = sum(image[:, [i for i in range(line - math.floor(n_lines/2), line + math.ceil(n_lines/2))]].transpose())
        # Eli's comment - need some work here
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
            # deviation = -(coeff[1] - center_point)
            piezo_diff = deviation  # * 0.0855

            curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
            # print(curr_value, piezo_diff, coeff[1])
            self.gui.hhm.pitch.move(curr_value - piezo_diff)

    def adjust_center_point(self, line=420, center_point=655, n_lines=1, n_measures=10):
        # getting center:
        centers = []
        for i in range(n_measures):
            image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))

            image = image.astype(np.int16)
            sum_lines = sum(
                image[:, [i for i in range(line - math.floor(n_lines / 2), line + math.ceil(n_lines / 2))]].transpose())
            # remove background (do it better later)
            if len(sum_lines) > 0:
                sum_lines = sum_lines - (sum(sum_lines) / len(sum_lines))

            index_max = sum_lines.argmax()
            max_value = sum_lines.max()
            min_value = sum_lines.min()
            # print('n_lines * 100: {} | max_value: {} | ((max_value - min_value) / n_lines): {}'.format(n_lines, max_value, ((max_value - min_value) / n_lines)))
            if max_value >= 10 and max_value <= n_lines * 100 and ((max_value - min_value) / n_lines) > 5:
                coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
                centers.append(960 - coeff[1])
        # print('Centers: {}'.format(centers))
        # print('Old Center Point: {}'.format(center_point))
        if len(centers) > 0:
            center_point = float(sum(centers) / len(centers))
            self.gui.settings.setValue('piezo_center', center_point)
            self.gui.piezo_center = center_point
            self.gui.hhm.fb_center.put(self.gui.piezo_center)
            # print('New Center Point: {}'.format(center_point))

    def run(self):
        self.go = 1
        # self.adjust_center_point(line = self.gui.piezo_line, center_point = self.gui.piezo_center, n_lines = self.gui.piezo_nlines, n_measures = self.gui.piezo_nmeasures)

        while (self.go):
            if len([self.gui.shutters[shutter] for shutter in self.gui.shutters if
                    self.gui.shutters[shutter].shutter_type != 'SP' and
                                    self.gui.shutters[shutter].state.read()['{}_state'.format(shutter)][
                                        'value'] != 0]) == 0:
                self.gaussian_piezo_feedback(line=self.gui.piezo_line, center_point=self.gui.piezo_center,
                                             n_lines=self.gui.piezo_nlines, n_measures=self.gui.piezo_nmeasures)
                ttime.sleep(self.sampleTime)
            else:
                ttime.sleep(self.sampleTime)
