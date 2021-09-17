import math
import time as ttime
from datetime import datetime

import bluesky.plan_stubs as bps
import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from bluesky.callbacks import LivePlot
from isstools.dialogs import (UpdateHHMFeedbackSettings, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box, message_box
from matplotlib.widgets import Cursor
from isstools.elements.liveplots import NormPlot
import json
from isstools.elements.figure_update import update_figure, setup_figure
from xas.energy_calibration import validate_calibration, process_calibration

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_setup.ui')


class UIBeamlineSetup(*uic.loadUiType(ui_path)):
    def __init__(self,
                    RE,
                    hhm,
                    hhm_feedback,
                    apb,
                    apb_trigger_xs,
                    apb_trigger_pil100k,
                    db,
                    db_proc,
                    detector_dictionary,
                    ic_amplifiers,
                    plan_funcs,
                    service_plan_funcs,
                    aux_plan_funcs,
                    motor_dictionary,
                    tune_elements,
                    shutter_dictionary,
                    parent_gui,
                    *args,

    ** kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.hhm = hhm
        self.hhm_feedback = hhm_feedback
        self.trajectory_manager = self.parent_gui.widget_trajectory_manager.traj_manager
        self.apb = apb
        self.apb_trigger_xs = apb_trigger_xs
        self.apb_trigger_pil100k = apb_trigger_pil100k
        self.db = db
        self.db_proc = db_proc
        self.detector_dictionary = detector_dictionary
        self.ic_amplifiers = ic_amplifiers
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        self.shutter_dictionary = shutter_dictionary
        self.parent_gui = parent_gui

        self.settings = QSettings(self.parent_gui.window_title, 'XLive')

        self.tune_elements = tune_elements

        #self.motor_list = self.motor_dictionary.keys()
        self.motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary]
        self.motor_sorted_list = list(self.motor_list)
        self.motor_sorted_list.sort()

        self.user_motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary
                         if ('user' in  self.motor_dictionary[motor].keys()) and self.motor_dictionary[motor]['user']]

        self.user_motor_sorted_list = list(self.user_motor_list)
        self.user_motor_sorted_list.sort()


        self.push_prepare_beamline.clicked.connect(self.prepare_beamline)
        self.push_get_offsets.clicked.connect(self.get_offsets)

        self.push_adjust_gains.clicked.connect(self.adjust_gains)
        self.push_bender_scan.clicked.connect(self.bender_scan)


        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.push_tune_beamline.clicked.connect(self.tune_beamline)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.detector_dictionary = detector_dictionary
        self.det_list = list(detector_dictionary.keys())

        self.comboBox_detectors.addItems(self.det_list)
        self.comboBox_detectors_den.addItem('1')
        self.comboBox_detectors_den.addItems(self.det_list)

        self.comboBox_detectors.currentIndexChanged.connect(self.detector_selected)
        self.comboBox_detectors_den.currentIndexChanged.connect(self.detector_selected_den)
        self.detector_selected()
        self.detector_selected_den()

        self.pushEnableHHMFeedback.setChecked(self.hhm_feedback.status)
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)
        self.push_update_feedback_settings.clicked.connect(self.update_hhm_feedback_settings)
        self.push_increase_fb_center.clicked.connect(self.feedback_center_increase)
        self.push_decrease_fb_enter.clicked.connect(self.feedback_center_decrease)
        self.push_update_feedback_center.clicked.connect(self.update_piezo_center)
        self.push_calibration_scan.clicked.connect(self.energy_calibration)

        # self.timer_update_fb_gui = QtCore.QTimer(self)
        # self.timer_update_fb_gui.setInterval(500)
        # self.timer_update_fb_gui.timeout.connect(self.update_feedback_gui_components)
        # self.timer_update_fb_gui.start()

        if 'Endstation BPM' in self.detector_dictionary:
            self.bpm_es = self.detector_dictionary['Endstation BPM']['device']

        self.figure_gen_scan, self.canvas_gen_scan, self.toolbar_gen_scan = setup_figure(self, self.plot_gen_scan)
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75)
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        self.checkBox_user_motors.toggled.connect(self.add_motors)
        self.add_motors()

        daq_rate = self.apb.acq_rate.get()
        self.spinBox_daq_rate.setValue(daq_rate)
        self.spinBox_daq_rate.valueChanged.connect(self.update_daq_rate)

        enc_rate_in_points = hhm.enc.filter_dt.get()
        enc_rate = 1/(89600*10*1e-9)/1e3
        self.spinBox_enc_rate.setValue(enc_rate)
        self.spinBox_enc_rate.valueChanged.connect(self.update_enc_rate)

        trigger_pil100k_freq = self.apb_trigger_pil100k.freq.get()
        self.spinBox_trigger_pil100k_freq.setValue(trigger_pil100k_freq)
        self.spinBox_trigger_pil100k_freq.valueChanged.connect(self.update_trigger_pil100k_freq)

        trigger_xs_freq = self.apb_trigger_xs.freq.get()
        self.spinBox_trigger_xs_freq.setValue(trigger_xs_freq)
        self.spinBox_trigger_xs_freq.valueChanged.connect(self.update_trigger_xs_freq)

        with open('/nsls2/xf08id/settings/json/foil_wheel.json') as fp:
            foil_info = json.load(fp)
            reference_foils = [item['element'] for item in foil_info]
            edges = [item['edge'] for item in foil_info]
            self.edge_dict={}
            for foil, edge in zip(reference_foils, edges):
                self.edge_dict[foil]= edge
            reference_foils.append('--')
        for foil in reference_foils:
            self.comboBox_reference_foils.addItem(foil)


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
            for shutter in [self.shutter_dictionary[shutter] for shutter in self.shutter_dictionary if
                            self.shutter_dictionary[shutter].shutter_type != 'SP']:
                if shutter.state.get():
                    ret = question_message_box(self,'Photon shutter closed', 'Proceed with the shutter closed?')
                    if not ret:
                        print('Aborted!')
                        return False
                    break

        if curr_element is not None:
            self.comboBox_detectors.setCurrentText(curr_element['det_name'])
            self.comboBox_channels.setCurrentText(curr_element['det_sig'])
            self.comboBox_detectors_den.setCurrentText('1')
            self.comboBox_motors.setCurrentText(self.motor_dictionary[curr_element['motor_name']]['description'])
            self.edit_gen_range.setText(str(curr_element['scan_range']))
            self.edit_gen_step.setText(str(curr_element['step_size']))


        curr_det = ''
        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)
        detectors = []
        detector_name = self.comboBox_detectors.currentText()
        detector = self.detector_dictionary[detector_name]['device']
        detectors.append(detector)
        channels = self.detector_dictionary[detector_name]['channels']
        channel = channels[self.comboBox_channels.currentIndex()]
        result_name = channel

        detector_name_den = self.comboBox_detectors_den.currentText()
        if detector_name_den != '1':
            detector_den = self.detector_dictionary[detector_name_den]['device']
            channels_den = self.detector_dictionary[detector_name_den]['channels']
            channel_den = channels_den[self.comboBox_channels.currentIndex()]
            detectors.append(detector_den)
            result_name += '/{}'.format(channel_den)
        else:
            channel_den = '1'

        for i in range(self.comboBox_detectors.count()):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'], 'dev_name'):
                if self.comboBox_detectors.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].dev_name.get():
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detectors.append(curr_det)
                if self.comboBox_detectors_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].dev_name.get():
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detectors.append(curr_det)
            else:
                if self.comboBox_detectors.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detectors.append(curr_det)
                if self.comboBox_detectors_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detectors.append(curr_det)

        #curr_mot = self.motor_dictionary[self.comboBox_gen_mot.currentText()]['object']
        for motor in self.motor_dictionary:
            if self.comboBox_motors.currentText() == self.motor_dictionary[motor]['description']:
                curr_mot = self.motor_dictionary[motor]['object']
                self.canvas_gen_scan.motor = curr_mot
                break



        rel_start = -float(self.edit_gen_range.text()) / 2
        rel_stop = float(self.edit_gen_range.text()) / 2
        num_steps = int(round(float(self.edit_gen_range.text()) / float(self.edit_gen_step.text()))) + 1

        update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan,self.canvas_gen_scan)

        #self.push_gen_scan.setEnabled(False)
        #print(channel, channel_den, result_name, curr_mot.name)
        uid_list = self.RE(self.aux_plan_funcs['general_scan'](detectors,
                                                               curr_mot,
                                                               rel_start,
                                                               rel_stop,
                                                               num_steps, ),
                           NormPlot(channel, channel_den, result_name, curr_mot.name, ax=self.figure_gen_scan.ax))

        # except Exception as exc:
        #     print('[General Scan] Aborted! Exception: {}'.format(exc))
        #     print('[General Scan] Limit switch reached . Set narrower range and try again.')
        #     uid_list = []

        self.figure_gen_scan.tight_layout()
        self.canvas_gen_scan.draw_idle()
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        #self.push_gen_scan.setEnabled(True)
        self.last_gen_scan_uid = self.db[-1]['start']['uid']
        self.push_gen_scan_save.setEnabled(True)

    def getX_gen_scan(self, event):

        if event.button == 3:
            if self.canvas_gen_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_gen_scan.motor,
                                                      parent=self.canvas_gen_scan)
                if dlg.exec_():
                    pass

    def tune_beamline(self):
        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)
        self.canvas_gen_scan.motor = ''
        print(f'[Beamline tuning] Starting...', file=self.parent_gui.emitstream_out, flush=True )
        self.pushEnableHHMFeedback.setChecked(False)
        self.RE(bps.mv(self.detector_dictionary['Focusing mirror BPM']['device'],'insert'))
        previous_detector = ''
        previous_motor = ''
        self.RE(bps.sleep(1))


        for element in self.tune_elements:
            print(f'[Beamline tuning] {element["comment"]}')
            detector = self.detector_dictionary[element['detector']]['device']
            motor = self.motor_dictionary[element['motor']]['object']

            if (detector.name != previous_detector) or (motor.name != previous_motor):
                update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan, self.canvas_gen_scan)

            self.RE(self.aux_plan_funcs['tuning_scan'](motor, detector,
                                                       element['range'],
                                                       element['step'],
                                                       retries=element['retries'],
                                                       stdout=self.parent_gui.emitstream_out
                                                       ),
                    LivePlot(detector.hints['fields'][0], x=motor.name, ax=self.figure_gen_scan.ax))
            # turn camera into continuous mode
            if hasattr(detector, 'image_mode'):
                self.RE(bps.mv(getattr(detector, 'image_mode'), 2))
                self.RE(bps.mv(getattr(detector, 'acquire'), 1))
            previous_detector = detector.name
            previous_motor = motor.name

        self.RE(bps.mv(self.detector_dictionary['Focusing mirror BPM']['device'], 'retract'))
        if self.checkBox_autoEnableFeedback.isChecked():
            self.update_piezo_center()
            self.pushEnableHHMFeedback.setChecked(True)

        print('[Beamline tuning] Beamline tuning complete',file=self.parent_gui.emitstream_out, flush=True)

    def bender_scan(self):
        message_box('Insert reference sample', 'Please ensure that a reference sample in inserted')
        print(f'[Bender scan] Starting...', file=self.parent_gui.emitstream_out, flush=True)
        self.RE(self.aux_plan_funcs['bender_scan']())
        print(f'[Bender scan] Complete...', file=self.parent_gui.emitstream_out, flush=True)

    def detector_selected(self):
        self.comboBox_channels.clear()
        detector = self.comboBox_detectors.currentText()
        self.comboBox_channels.addItems(self.detector_dictionary[detector]['channels'])

    def detector_selected_den(self):
        self.comboBox_channels_den.clear()
        detector = self.comboBox_detectors_den.currentText()
        if detector == '1':
            self.comboBox_channels_den.addItem('1')
        else:
            self.comboBox_channels_den.addItems(self.detector_dictionary[detector]['channels'])

    def adjust_gains(self):
        detectors = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        self.RE(self.service_plan_funcs['adjust_ic_gains'](detector_names=detectors, stdout = self.parent_gui.emitstream_out))

    def prepare_beamline(self, energy_setting=None):
        if energy_setting:
            self.lineEdit_energy.setText(str(energy_setting))
        self.RE(self.service_plan_funcs['prepare_beamline_plan'](energy=float(self.lineEdit_energy.text()),
                                                                stdout = self.parent_gui.emitstream_out))

    def get_offsets(self):
        self.RE(self.service_plan_funcs['get_offsets']())

    def add_motors(self):
        self.comboBox_motors.clear()
        if self.checkBox_user_motors.isChecked():
            self.comboBox_motors.addItems(self.user_motor_sorted_list)
        else:
            self.comboBox_motors.addItems(self.motor_sorted_list)

    def enable_fb(self, value):
        value = value > 0
        self.hhm.fb_status.put(int(value))
        self.pushEnableHHMFeedback.setChecked(value)

    def update_hhm_feedback_settings(self):
        pars = self.hhm_feedback.current_fb_parameters()
        pars_str = [str(i) for i in pars]
        dlg = UpdateHHMFeedbackSettings.UpdatePiezoDialog(*pars_str, parent=self)
        if dlg.exec_():
            new_pars = dlg.getValues()
            self.hhm_feedback.set_fb_parameters(*new_pars)

    def feedback_center_increase(self):
        self.hhm_feedback.tweak_fb_center(1)

    def feedback_center_decrease(self):
        self.hhm_feedback.tweak_fb_center(-1)

    def update_piezo_center(self):
        self.hhm_feedback.update_center()


    def update_daq_rate(self):
        daq_rate = self.spinBox_daq_rate.value()
        # 374.94 is the nominal RF frequency
        divider = int(374.94/daq_rate)
        self.RE(bps.abs_set(self.apb.divide, divider, wait=True))

    def update_enc_rate(self):
        enc_rate = self.spinBox_enc_rate.value()
        rate_in_points = (1/(enc_rate*1e3))*1e9/10

        rate_in_points_rounded = int(np.ceil(rate_in_points / 100.0) * 100)
        self.RE(bps.abs_set(self.hhm.enc.filter_dt, rate_in_points_rounded, wait=True))

    def update_trigger_pil100k_freq(self):
        trigger_pil100k_freq = self.spinBox_trigger_pil100k_freq.value()
        self.apb_trigger_pil100k.freq.put(trigger_pil100k_freq)

    def update_trigger_xs_freq(self):
        trigger_xs_freq = self.spinBox_trigger_xs_freq.value()
        self.apb_trigger_xs.freq.put(trigger_xs_freq)

    def energy_calibration(self):
        element = self.comboBox_reference_foils.currentText()
        edge = self.edge_dict[element]
        st, message = validate_calibration(element, edge, self.db_proc,self.hhm)
        if st:
            self.RE(self.aux_plan_funcs['set_reference_foil'](element))
            self.RE(self.plan_funcs['Fly scan'](f'{element} {edge} foil scan', ''))
            e_shift, en_ref, mu_ref, mu = process_calibration(element, edge, self.db,self.db_proc, self.hhm, self.trajectory_manager)
            self._update_figure_with_calibration_data(en_ref, mu_ref, mu)
            print(f'{ttime.ctime()} [Energy calibration] Energy shift is {e_shift} eV')

            print(f'{ttime.ctime()} [Energy calibration] Validating the calibration')
            self.RE(self.plan_funcs['Fly scan'](f'{element} {edge} foil scan', ''))
            e_shift, en_ref, mu_ref, mu = process_calibration(self.db, self.db_proc, self.hhm)
            if e_shift < 0.1:
                print(f'{ttime.ctime()} [Energy calibration] Completed')

            else:
                print(f'{ttime.ctime()} [Energy calibration] Energy calibration error is {e_shift} > 0.1 eV. Check Manually.')
            self._update_figure_with_calibration_data(en_ref, mu_ref, mu)

        else:
            message_box('Error', message)


    def _update_figure_with_calibration_data(self, en_ref, mu_ref, mu):
        self.figure_gen_scan.ax.plot(en_ref, mu_ref, label='Reference')
        self.figure_gen_scanax.plot(en_ref, mu, label='New spectrum')
        self.figure_gen_scan.ax.set_xlabel('Energy')
        self.figure_gen_scan.ax.set_ylabel('mu')
        self.figure_gen_scan.ax.set_xlim(en_ref[0], en_ref[-1])
        self.figure_gen_scan.legend(loc='upper left')
        self.figure_gen_scan.tight_layout()
        self.canvas_gen_scan.draw_idle()
        self.canvas_gen_scan.motor = None


# class piezo_fb_thread(QThread):
#     def __init__(self, gui):
#         QThread.__init__(self)
#         self.gui = gui
#
#         P = 0.004 * self.gui.piezo_kp
#         I = 0  # 0.02
#         D = 0  # 0.01
#         self.pid = PID(P, I, D)
#         # self.sampleTime = 0.00025
#         self.sampleTime = 0.01 # Denis testing on May 25, 2021
#         self.pid.setSampleTime(self.sampleTime)
#         self.pid.windup_guard = 3
#         self.go = 0
#         self.should_print_diagnostics = True
#         self.truncate_data = False
#
#     def determine_beam_position_from_image(self, line = 420, center_point = 655, n_lines = 1):
#         try:
#
#             image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))
#
#         except Exception as e:
#             print(f"Exception: {e}\nPlease, check the max retries value in the piezo feedback IOC or maybe the network load (too many cameras).")
#             return
#
#         return determine_beam_position_from_fb_image(image, line=line, center_point=center_point, n_lines=n_lines, truncate_data=self.truncate_data,
#                                                      should_print_diagnostics=self.should_print_diagnostics)
#
#
#     def gaussian_piezo_feedback(self, line = 420, center_point = 655, n_lines = 1, n_measures = 10):
#
#         current_position = self.determine_beam_position_from_image(line = line, center_point = center_point, n_lines = n_lines)
#         # print(f'current position: {current_position}')
#         if current_position:
#             self.pid.SetPoint = 960 - center_point
#             self.pid.update(current_position)
#             deviation = self.pid.output
#             # deviation = -(coeff[1] - center_point)
#             piezo_diff = deviation  # * 0.0855
#
#             curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
#             # print(f"{ttime.ctime()} curr_value: {curr_value}, piezo_diff: {piezo_diff}, delta: {curr_value - piezo_diff}")
#             try:
#                 self.gui.hhm.pitch.move(curr_value - piezo_diff)
#                 self.should_print_diagnostics = True
#             except:
#                 if self.should_print_diagnostics:
#                     print('failed to correct pitch due to controller bug (DSSI works on it)')  # TODO: Denis 5/25/2021
#                     self.should_print_diagnostics = False
#         else:
#             self.should_print_diagnostics = False
#
#     def adjust_center_point(self, line=420, center_point=655, n_lines=1, n_measures=10):
#         # getting center:
#         centers = []
#         #print(f'center_point INITIALLY is {center_point}')
#         for i in range(n_measures):
#             current_position = self.determine_beam_position_from_image(line=line, center_point=center_point,
#                                                                        n_lines=n_lines)
#             if current_position:
#                 centers.append(960 - current_position)
#         # print('Centers: {}'.format(centers))
#         # print('Old Center Point: {}'.format(center_point))
#         if len(centers) > 0:
#             center_point = np.mean(centers)
#             print(f'center_point DETERMINED is {center_point}')
#             self.gui.settings.setValue('piezo_center', center_point)
#             self.gui.piezo_center = center_point
#             self.gui.hhm.fb_center.put(self.gui.piezo_center)
#             # print('New Center Point: {}'.format(center_point))
#
#     def run(self):
#         self.go = 1
#         # self.adjust_center_point(line = self.gui.piezo_line, center_point = self.gui.piezo_center, n_lines = self.gui.piezo_nlines, n_measures = self.gui.piezo_nmeasures)
#
#         while (self.go):
#             # print("Here all the time? 1")
#             if len([self.gui.shutter_dictionary[shutter] for shutter in self.gui.shutter_dictionary if
#                     self.gui.shutter_dictionary[shutter].shutter_type != 'SP' and
#                                     self.gui.shutter_dictionary[shutter].state.read()['{}_state'.format(shutter)][
#                                         'value'] != 0]) == 0:
#                 self.gaussian_piezo_feedback(line=self.gui.piezo_line, center_point=self.gui.piezo_center,
#                                              n_lines=self.gui.piezo_nlines, n_measures=self.gui.piezo_nmeasures)
#                 # print("Here all the time? 4")
#                 ttime.sleep(self.sampleTime)
#                 # print("Here all the time? 5")
#             else:
#                 # print("Here all the time? Not here!")
#                 ttime.sleep(self.sampleTime)


