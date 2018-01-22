import pkg_resources
import json

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from scipy.optimize import curve_fit

from datetime import datetime
import numpy as np
import time as ttime
from subprocess import call
import re
import pandas as pd
import math

from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from scipy.optimize import curve_fit
import math
import signal

from isstools.pid import PID
from isstools.dialogs import (UpdatePiezoDialog, Prepare_BL_Dialog, MoveMotorDialog)

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_setup.ui')


class UIBeamlineSetup(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 hhm,
                 db,
                 adc_list,
                 enc_list,
                 det_dict,
                 xia,
                 ic_amplifiers,
                 prepare_bl_plan,
                 plan_funcs,
                 prepare_bl_list,
                 set_gains_offsets_scan,
                 motors_dict,
                 general_scan_func,
                 create_log_scan,
                 auto_tune_dict,
                 shutters,
                 parent_gui,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.RE = RE
        self.hhm = hhm
        self.db = db
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.det_dict = det_dict
        self.xia = xia
        self.ic_amplifiers = ic_amplifiers
        self.prepare_bl_plan = prepare_bl_plan
        self.plan_funcs = plan_funcs
        self.prepare_bl_list = prepare_bl_list
        self.set_gains_offsets_scan = set_gains_offsets_scan
        self.motors_dict = motors_dict
        self.gen_scan_func = general_scan_func
        self.create_log_scan = create_log_scan
        self.auto_tune_dict = auto_tune_dict
        self.shutters = shutters
        self.parent_gui = parent_gui
        self.settings = QSettings('ISS Beamline', 'Xview')

        self.settings = QSettings('ISS Beamline', 'XLive')

        if self.auto_tune_dict is not None:
            self.auto_tune_elements = self.auto_tune_dict['elements']
            self.auto_tune_pre_elements = self.auto_tune_dict['pre_elements']
            self.auto_tune_post_elements = self.auto_tune_dict['post_elements']
        else:
            self.auto_tune_elements = None

        #self.mot_list = self.motors_dict.keys()
        self.mot_list = [self.motors_dict[motor]['description'] for motor in self.motors_dict]
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()

        if len(self.prepare_bl_list) == 2:
            self.prepare_bl_plan = self.prepare_bl_list[0]
            self.prepare_bl_def = self.prepare_bl_list[1]
        else:
            self.prepare_bl_plan = None

        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        if 'get_offsets' in self.plan_funcs_names:
            self.push_get_offsets.clicked.connect(self.run_get_offsets)
        else:
            self.push_get_offsets.setEnabled(False)

        if self.prepare_bl_plan is not None:
            self.plan_funcs.append(self.prepare_bl)
            self.plan_funcs_names.append(self.prepare_bl.__name__)

        self.plan_funcs.append(self.adjust_ic_gains)
        self.plan_funcs_names.append(self.adjust_ic_gains.__name__)
        if self.set_gains_offsets_scan is not None:
            self.plan_funcs.append(self.set_gains_offsets_scan)
            self.plan_funcs_names.append(self.set_gains_offsets_scan.__name__)

        if self.hhm is None:
            self.pushEnableHHMFeedback.setEnabled(False)
            self.update_piezo.setEnabled(False)

        if hasattr(hhm, 'fb_line'):
            self.fb_master = 0
            self.piezo_line = int(self.hhm.fb_line.value)
            self.piezo_center = float(self.hhm.fb_center.value)
            self.piezo_nlines = int(self.hhm.fb_nlines.value)
            self.piezo_nmeasures = int(self.hhm.fb_nmeasures.value)
            self.piezo_kp = float(self.hhm.fb_pcoeff.value)
            self.hhm.fb_status.subscribe(self.update_fb_status)
            self.piezo_thread = piezo_fb_thread(self) 
            self.update_piezo.clicked.connect(self.update_piezo_params)
            self.push_update_piezo_center.clicked.connect(self.update_piezo_center)


        json_data = open(pkg_resources.resource_filename('isstools', 'beamline_preparation.json')).read()
        self.json_blprep = json.loads(json_data)
        self.beamline_prep = self.json_blprep[0]
        self.fb_positions = self.json_blprep[1]['FB Positions']

        # Populate analog detectors setup section with adcs:
        self.adc_checkboxes = []
        for index, adc_name in enumerate([adc.dev_name.value for adc in
                                          self.adc_list if adc.dev_name.value != adc.name]):
            checkbox = QtWidgets.QCheckBox(adc_name)
            checkbox.setChecked(True)
            self.adc_checkboxes.append(checkbox)
            self.gridLayout_analog_detectors.addWidget(checkbox, int(index / 2), index % 2)

        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.push_gen_scan_save.clicked.connect(self.save_gen_scan)
        self.push_prepare_autotune.clicked.connect(self.autotune_function)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.det_list = [det_dict[det]['obj'].dev_name.value if hasattr(det_dict[det]['obj'], 'dev_name') else det_dict[det]['obj'].name for det in det_dict]
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
        if 'bpm_es' in self.det_dict:
            self.bpm_es = self.det_dict['bpm_es']['obj']
            found_bpm = 1

        if found_bpm == 0 or self.hhm is None:
            self.pushEnableHHMFeedback.setEnabled(False)
            self.update_piezo.setEnabled(False)

        if len(self.mot_sorted_list) == 0 or len(self.det_sorted_list) == 0 or self.gen_scan_func == None:
            self.push_gen_scan.setEnabled(0)

        if self.auto_tune_elements is not None:
            tune_elements = ' | '.join([element['name'] for element in self.auto_tune_elements])
            self.push_prepare_autotune.setToolTip(
                'Elements: ({})\nIf the parameters are not defined, it will use parameters from General Scans boxes (Scan Range, Step Size and Max Retries)'.format(
                    tune_elements))
        else:
            self.push_prepare_autotune.setEnabled(False)

        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)
        self.run_check_gains.clicked.connect(self.run_gains_test)
        self.run_check_gains_scan.clicked.connect(self.adjust_ic_gains)

        if self.prepare_bl_plan is not None:
            self.push_prepare_bl.clicked.connect(self.prepare_bl_dialog)
            self.push_prepare_bl.setEnabled(True)
        else:
            self.push_prepare_bl.setEnabled(False)

        if hasattr(self.hhm, 'fb_status'):
            self.pushEnableHHMFeedback.setChecked(self.hhm.fb_status.value)
            self.radioButton_fb_local.setEnabled(not self.hhm.fb_status.value)
            self.radioButton_fb_remote.setEnabled(not self.hhm.fb_status.value)
            self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)
            self.pushEnableHHMFeedback.toggled.connect(self.radioButton_fb_local.setDisabled)
            self.pushEnableHHMFeedback.toggled.connect(self.radioButton_fb_remote.setDisabled)
        else:
            self.pushEnableHHMFeedback.setEnabled(False)
            self.radioButton_fb_local.setEnabled(False)
            self.radioButton_fb_remote.setEnabled(False)

        if self.ic_amplifiers is None:
            self.run_check_gains_scan.setEnabled(False)

        if len(self.adc_list):
            times_arr = np.array(list(self.adc_list[0].averaging_points.enum_strs))
            times_arr[times_arr == ''] = 0.0
            times_arr = list(times_arr.astype(np.float) * self.adc_list[0].sample_rate.value / 100000)
            times_arr = [str(elem) for elem in times_arr]
            self.comboBox_samp_time.addItems(times_arr)
            self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_batch_mode.setAnalogSampTime)
            self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_run.setAnalogSampTime)
            self.comboBox_samp_time.setCurrentIndex(self.adc_list[0].averaging_points.value)

        if len(self.enc_list):
            self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_batch_mode.setEncSampTime)
            self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_run.setEncSampTime)
            self.lineEdit_samp_time.setText(str(self.enc_list[0].filter_dt.value / 100000))

        if hasattr(self.xia, 'input_trigger'):
            if self.xia.input_trigger is not None:
                self.xia.input_trigger.unit_sel.put(1)  # ms, not us
                self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_batch_mode.setXiaSampTime)
                self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_run.setXiaSampTime)
                self.lineEdit_xia_samp.setText(str(self.xia.input_trigger.period_sp.value))

        self.dets_with_amp = [self.det_dict[det]['obj'] for det in self.det_dict
                             if self.det_dict[det]['obj'].name[:3] == 'pba' and hasattr(self.det_dict[det]['obj'], 'amp')]
        if self.dets_with_amp == []:
            self.push_read_amp_gains.setEnabled(False)
        else:
            self.push_read_amp_gains.clicked.connect(self.read_amp_gains)

    def addCanvas(self):
        self.figure_gen_scan = Figure()
        self.figure_gen_scan.set_facecolor(color='#FcF9F6')
        self.canvas_gen_scan = FigureCanvas(self.figure_gen_scan)
        self.canvas_gen_scan.motor = ''
        self.figure_gen_scan.ax = self.figure_gen_scan.add_subplot(111)
        self.toolbar_gen_scan = NavigationToolbar(self.canvas_gen_scan, self, coordinates=True)
        self.plot_gen_scan.addWidget(self.toolbar_gen_scan)
        self.plot_gen_scan.addWidget(self.canvas_gen_scan)
        self.canvas_gen_scan.draw_idle()
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75)

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
                        print('Aborted!')
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
        detectors = []

        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)

        for i in range(self.comboBox_gen_det.count()):
            if hasattr(self.det_dict[list(self.det_dict.keys())[i]]['obj'], 'dev_name'):
                if self.comboBox_gen_det.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detectors.append(curr_det)
            else:
                if self.comboBox_gen_det.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].name:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].name:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detectors.append(curr_det)

        #curr_mot = self.motors_dict[self.comboBox_gen_mot.currentText()]['object']
        for motor in self.motors_dict:
            if self.comboBox_gen_mot.currentText() == self.motors_dict[motor]['description']:
                curr_mot = self.motors_dict[motor]['object']
                break

        if curr_det == '':
            print('Detector not found. Aborting...')
            raise Exception('Detector not found')

        if curr_mot == '':
            print('Motor not found. Aborting...')
            raise Exception('Motor not found')

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
                                               retries=self.spinBox_gen_scan_retries.value(),
                                               ax=self.figure_gen_scan.ax))
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

    def save_gen_scan(self):
        run = self.db[self.last_gen_scan_uid]
        self.user_directory = '/GPFS/xf08id/User Data/{}.{}.{}/' \
            .format(run['start']['year'],
                    run['start']['cycle'],
                    run['start']['PROPOSAL'])

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

    def getX_gen_scan(self, event):
        if event.button == 3:
            if self.canvas_gen_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_gen_scan.motor,
                                                      parent=self.canvas_gen_scan)
                if dlg.exec_():
                    pass

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

    def process_detsig(self):
        self.comboBox_gen_detsig.clear()
        for i in range(self.comboBox_gen_det.count()):
            if hasattr(self.det_dict[list(self.det_dict.keys())[i]]['obj'], 'dev_name'):#hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detsig = self.det_dict[list(self.det_dict.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)
            else:
                if self.comboBox_gen_det.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].name:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detsig = self.det_dict[list(self.det_dict.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)

    def process_detsig_den(self):
        self.comboBox_gen_detsig_den.clear()
        for i in range(self.comboBox_gen_det_den.count() - 1):
            if hasattr(self.det_dict[list(self.det_dict.keys())[i]]['obj'], 'dev_name'):#hasattr(list(self.det_dict.keys())[i], 'dev_name'):
                if self.comboBox_gen_det_den.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detsig = self.det_dict[list(self.det_dict.keys())[i]]['elements']
                    self.comboBox_gen_detsig_den.addItems(detsig)
            else:
                if self.comboBox_gen_det_den.currentText() == self.det_dict[list(self.det_dict.keys())[i]]['obj'].name:
                    curr_det = self.det_dict[list(self.det_dict.keys())[i]]['obj']
                    detsig = self.det_dict[list(self.det_dict.keys())[i]]['elements']
                    self.comboBox_gen_detsig_den.addItems(detsig)
        if self.comboBox_gen_det_den.currentText() == '1':
            self.comboBox_gen_detsig_den.addItem('1')
            self.checkBox_tune.setEnabled(True)
        else:
            self.checkBox_tune.setChecked(False)
            self.checkBox_tune.setEnabled(False)

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

    def adjust_ic_gains(self, trajectory: int = -1):

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

        # while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 0:
        #        QtWidgets.QApplication.processEvents()
        #        ttime.sleep(0.1)

        signal.alarm(0)

        current_adc_index = self.comboBox_samp_time.currentIndex()
        current_enc_value = self.lineEdit_samp_time.text()

        info = self.parent_gui.widget_trajectory_manager.traj_manager.read_info(silent=True)

        if 'max' not in info[str(current_lut)] or 'min' not in info[str(current_lut)]:
            raise Exception(
                'Could not find max or min information in the trajectory. Try sending it again to the controller.')

        min_en = int(info[str(current_lut)]['min'])
        max_en = int(info[str(current_lut)]['max'])

        edge_energy = int(round((max_en + min_en) / 2))
        preedge_lo = min_en - edge_energy
        postedge_hi = max_en - edge_energy

        self.parent_gui.widget_trajectory_manager.traj_creator.define(edge_energy=edge_energy, offsets=[preedge_lo, 0, 0, postedge_hi], sine_duration=2.5,
                                 trajectory_type='Sine')
        self.parent_gui.widget_trajectory_manager.traj_creator.interpolate()
        self.parent_gui.widget_trajectory_manager.traj_creator.tile(reps=1)
        self.parent_gui.widget_trajectory_manager.traj_creator.e2encoder(0)  # float(self.RE.md['angle_offset']))
        # Don't need the offset since we're getting the data already with the offset

        if not len(self.parent_gui.widget_trajectory_manager.traj_creator.energy_grid):
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
                   self.parent_gui.widget_trajectory_manager.traj_creator.energy_grid, fmt='%.6f')
        call(['chmod', '666', filename])

        self.parent_gui.widget_trajectory_manager.traj_manager.load(orig_file_name=filename[filename.rfind('/') + 1:],
                               new_file_path='9', is_energy=True,
                               offset=float(self.hhm.angle_offset.value))

        ttime.sleep(1)

        self.parent_gui.widget_trajectory_manager.traj_manager.init(9)

        not_done = 1
        max_tries = 1
        while not_done and max_tries:
            not_done = 0
            max_tries -= 1

            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'closed']:
                shutter.open()

            for func in self.plan_funcs:
                if func.__name__ == 'tscan':
                    tscan_func = func
                    break
            self.current_uid_list = list(tscan_func('Check gains', ''))

            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'SP' and self.shutters[shutter].state == 'open']:
                shutter.close()

            # Send sampling time to the pizzaboxes:
            self.comboBox_samp_time.setCurrentIndex(current_adc_index)
            self.current_enc_value = self.lineEdit_samp_time.setText(current_enc_value)
            value = int(
                round(float(self.comboBox_samp_time.currentText()) / self.adc_list[0].sample_rate.value * 100000))
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
                data = pd.DataFrame(np.array(data)[25:-25, 3])[0].apply(lambda x: (x >> 8) - 0x40000
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
                                print_message += '{} is always positive. Perhaps it\'s floating.\n'.format(
                                    devnames[index])
                            elif data.min() > saturation / 100:
                                exp += 2
                                print_message += 'Increasing {} gain by 10^2. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            elif data.min() > saturation / 10:
                                exp += 1
                                print_message += 'Increasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            elif data.max() < 0.5 and data.min() > saturation:
                                print_message += '{} seems to be configured properly. Current gain: 10^{}\n'.format(
                                    devnames[index], exp)
                            elif data.min() <= saturation:
                                exp -= 1
                                print_message += 'Decreasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            else:
                                print_message += '{} got a case that the programmer wasn\'t expecting. Sorry.\n'.format(
                                    devnames[index])

                            if (data.min() > saturation / 10 or data.min() < saturation) and not (
                                    data.max() > 0 and data.min() > 0):
                                not_done = 1
                                self.ic_amplifiers['{}_amp'.format(devnames[index])].set_gain(exp, high_speed=curr_hs)

                        elif curr_amp.par.polarity == 'pos':
                            if (data > saturation).sum() < len(data) * 0.01:
                                data[data > saturation] = data.mean()
                            print('{}:   Max = {}   Min = {}'.format(devnames[index], data.max(), data.min()))

                            if data.max() < 0 and data.min() < 0:
                                print_message += '{} is always negative. Perhaps it\'s floating.\n'.format(
                                    devnames[index])
                            elif data.max() < saturation / 100:
                                exp += 2
                                print_message += 'Increasing {} gain by 10^2. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            elif data.max() < saturation / 10:
                                exp += 1
                                print_message += 'Increasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            elif data.min() > -0.5 and data.max() < saturation:
                                print_message += '{} seems to be configured properly. Current gain: 10^{}\n'.format(
                                    devnames[index], exp)
                            elif data.max() >= saturation:
                                exp -= 1
                                print_message += 'Decreasing {} gain by 10^1. New gain: 10^{}\n'.format(devnames[index],
                                                                                                        exp)
                            else:
                                print_message += '{} got a case that the programmer wasn\'t expecting. Sorry.\n'.format(
                                    devnames[index])

                            if (data.max() < saturation / 10 or data.max() > saturation) and not (
                                    data.min() < 0 and data.max() < 0):
                                not_done = 1
                                self.ic_amplifiers['{}_amp'.format(devnames[index])].set_gain(exp, high_speed=curr_hs)

                except Exception as exc:
                    print('Exception: {}'.format(exc))

            print('-' * 30)
            if print_message:
                print(print_message[:-1])
            print('-' * 30)

        self.parent_gui.widget_trajectory_manager.traj_manager.init(current_lut)

        print('[Gain set scan] Complete\n')

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

    def enable_fb(self, value):
        if self.radioButton_fb_local.isChecked():
            if value == 0:
                if self.piezo_thread.go != 0 or self.fb_master != 0 or self.hhm.fb_status.value != 0:
                    self.toggle_piezo_fb(0)
            else:
                if self.fb_master == -1:
                    return
                self.fb_master = 1
                self.toggle_piezo_fb(2)

        elif self.radioButton_fb_remote.isChecked():
            self.hhm.fb_status.put(value)

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
        if self.radioButton_fb_local.isChecked():
            if value:
                value = 2
            self.toggle_piezo_fb(value)

        elif self.radioButton_fb_remote.isChecked():
            self.pushEnableHHMFeedback.setChecked(value)

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
        if self.radioButton_fb_local.isChecked():
            nmeasures = self.piezo_nmeasures
            if nmeasures == 0:
                nmeasures = 1
            self.piezo_thread.adjust_center_point(line=self.piezo_line, 
                                                  center_point=self.piezo_center,
                                                  n_lines=self.piezo_nlines, 
                                                  n_measures=nmeasures)

        elif self.radioButton_fb_remote.isChecked():
            nmeasures = self.piezo_nmeasures
            if nmeasures == 0:
                nmeasures = 1
    
            # getting center:
            centers = []
            for i in range(nmeasures):
                image = self.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))
    
                image = image.astype(np.int16)
                sum_lines = sum(image[:, [i for i in range(self.piezo_line - math.floor(self.piezo_nlines / 2),
                                                           self.piezo_line + math.ceil(
                                                               self.piezo_nlines / 2))]].transpose())
    
                if len(sum_lines) > 0:
                    sum_lines = sum_lines - (sum(sum_lines) / len(sum_lines))
    
                index_max = sum_lines.argmax()
                max_value = sum_lines.max()
                min_value = sum_lines.min()
    
                if max_value >= 10 and max_value <= self.piezo_nlines * 100 and (
                    (max_value - min_value) / self.piezo_nlines) > 5:
                    coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
                    centers.append(960 - coeff[1])
    
            if len(centers) > 0:
                self.piezo_center = float(sum(centers) / len(centers))
                self.settings.setValue('piezo_center', self.piezo_center)
                self.hhm.fb_center.put(self.piezo_center)

    def gauss(self, x, *p):
        A, mu, sigma = p
        return A * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2))

    def read_amp_gains(self):
        adcs = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        if not len(adcs):
            print('[Read Gains] Please select one or more Analog detectors')
            return

        print('[Read Gains] Starting...')

        det_dict_with_amp = [self.det_dict[det]['obj'] for det in self.det_dict if hasattr(self.det_dict[det]['obj'], 'dev_name')]
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
        # if the feedback is too slow, check the max retries value in the piezo IOC or maybe the network load.
        #print("Here all the time? 2")
        try:
            image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))
        except Exception as e:
            print(f"Exception: {e}\nPlease, check the max retries value in the piezo feedback IOC or maybe the network load (too many cameras).")
            return

        image = image.astype(np.int16)
        sum_lines = sum(image[:, [i for i in range(line - math.floor(n_lines/2), line + math.ceil(n_lines/2))]].transpose())
        # Eli's comment - need some work here
        #remove background (do it better later)
        if len(sum_lines) > 0:
            sum_lines = sum_lines - (sum(sum_lines) / len(sum_lines))
        index_max = sum_lines.argmax()
        max_value = sum_lines.max()
        min_value = sum_lines.min()

        #print("Here all the time? 3")
        if max_value >= 10 and max_value <= n_lines * 100 and ((max_value - min_value) / n_lines) > 5:
            coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
            self.pid.SetPoint = 960 - center_point
            self.pid.update(coeff[1])
            deviation = self.pid.output
            # deviation = -(coeff[1] - center_point)
            piezo_diff = deviation  # * 0.0855

            curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
            #print(f"curr_value: {curr_value}, piezo_diff: {piezo_diff}, coeff[1]: {coeff[1]}")
            self.gui.hhm.pitch.move(curr_value - piezo_diff)

    def adjust_center_point(self, line=420, center_point=655, n_lines=1, n_measures=10):
        # getting center:
        centers = []
        for i in range(n_measures):
            try:
                image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))
            except Exception as e:
                print(f"Exception: {e}\nPlease, check the max retries value in the piezo feedback IOC or maybe the network load (too many cameras).")
                return

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
            #print("Here all the time? 1")
            if len([self.gui.shutters[shutter] for shutter in self.gui.shutters if
                    self.gui.shutters[shutter].shutter_type != 'SP' and
                                    self.gui.shutters[shutter].state.read()['{}_state'.format(shutter)][
                                        'value'] != 0]) == 0:
                self.gaussian_piezo_feedback(line=self.gui.piezo_line, center_point=self.gui.piezo_center,
                                             n_lines=self.gui.piezo_nlines, n_measures=self.gui.piezo_nmeasures)
                #print("Here all the time? 4")
                ttime.sleep(self.sampleTime)
                #print("Here all the time? 5")
            else:
                #print("Here all the time? Not here!")
                ttime.sleep(self.sampleTime)
