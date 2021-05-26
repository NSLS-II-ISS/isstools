import math
import time as ttime
from datetime import datetime

import bluesky.plan_stubs as bps
import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from bluesky.callbacks import LivePlot
from isstools.dialogs import (UpdatePiezoDialog, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from scipy.optimize import curve_fit
from xas.pid import PID
from xas.math import gauss
from isstools.elements.liveplots import NormPlot
import json
from xas.image_analysis import determine_beam_position_from_fb_image

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_setup.ui')


class UIBeamlineSetup(*uic.loadUiType(ui_path)):
    def __init__(self,
                     RE,
                     hhm,
                     db,
                     detector_dictionary,
                     ic_amplifiers,
                     service_plan_funcs,
                     aux_plan_funcs,
                     motor_dictionary,
                     tune_elements,
                     shutter_dictionary,
                     parent_gui,
                     *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.RE = RE
        self.hhm = hhm
        self.db = db
        self.detector_dictionary = detector_dictionary
        self.ic_amplifiers = ic_amplifiers
        self.service_plan_funcs = service_plan_funcs
        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        self.shutter_dictionary = shutter_dictionary
        self.parent_gui = parent_gui

        self.settings = QSettings(self.parent_gui.window_title, 'XLive')

        self.tune_elements = tune_elements

        #self.mot_list = self.motor_dictionary.keys()
        self.mot_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary]
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()


        self.push_prepare_beamline.clicked.connect(self.prepare_beamline)
        self.push_get_offsets.clicked.connect(self.get_offsets)
        self.push_get_readouts.clicked.connect(self.get_readouts)
        self.push_adjust_gains.clicked.connect(self.adjust_gains)

        if hasattr(hhm, 'fb_line'):
            self.fb_master = 0
            self.piezo_line = int(self.hhm.fb_line.get())
            self.piezo_center = float(self.hhm.fb_center.get())
            self.piezo_nlines = int(self.hhm.fb_nlines.get())
            self.piezo_nmeasures = int(self.hhm.fb_nmeasures.get())
            self.piezo_kp = float(self.hhm.fb_pcoeff.get())
            self.hhm.fb_status.subscribe(self.update_fb_status, run=False)
            self.piezo_thread = piezo_fb_thread(self)
            self.push_update_piezo.clicked.connect(self.update_piezo_params)
            self.push_increase_center.clicked.connect(self.fb_center_increase)
            self.push_decrease_center.clicked.connect(self.fb_center_decrease)
            self.push_update_piezo_center.clicked.connect(self.update_piezo_center)
            self.push_set_reference_foil.clicked.connect(self.set_reference_foil)

        # # Populate analog detectors setup section with adcs:
        # self.adc_checkboxes = []
        # for index, adc_name in enumerate([adc.dev_name.get() for adc in
        #                                   self.adc_list if adc.dev_name.get() != adc.name]):
        #     checkbox = QtWidgets.QCheckBox(adc_name)
        #     checkbox.setChecked(True)
        #     self.adc_checkboxes.append(checkbox)
        #     self.gridLayout_analog_detectors.addWidget(checkbox, int(index / 2), index % 2)

        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.push_tune_beamline.clicked.connect(self.tune_beamline)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.detector_dictionary = detector_dictionary
        self.det_list = list(detector_dictionary.keys())

        ## self.det_sorted_list = self.det_list
        # self.det_sorted_list.sort()

        self.comboBox_detectors.addItems(self.det_list)
        self.comboBox_detectors_den.addItem('1')
        self.comboBox_detectors_den.addItems(self.det_list)
        self.comboBox_motors.addItems(self.mot_sorted_list)
        self.comboBox_detectors.currentIndexChanged.connect(self.detector_selected)
        self.comboBox_detectors_den.currentIndexChanged.connect(self.detector_selected_den)
        self.detector_selected()
        self.detector_selected_den()

        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        self.pushEnableHHMFeedback.setChecked(self.hhm.fb_status.get())
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)

        if 'Endstation BPM' in self.detector_dictionary:
            self.bpm_es = self.detector_dictionary['Endstation BPM']['device']

        # if len(self.adc_list):
        #     times_arr = np.array(list(self.adc_list[0].averaging_points.enum_strs))
        #     times_arr[times_arr == ''] = 0.0
        #     times_arr = list(times_arr.astype(np.float) * self.adc_list[0].sample_rate.get() / 100000)
        #     times_arr = [str(elem) for elem in times_arr]
        #     self.comboBox_samp_time.addItems(times_arr)
        #     #   self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_batch_mode.setAnalogSampTime)
        #     self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_run.setAnalogSampTime)
        #     self.comboBox_samp_time.setCurrentIndex(self.adc_list[0].averaging_points.get())

        # if len(self.enc_list):
        #     #self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_batch_mode.setEncSampTime)
        #     self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_run.setEncSampTime)
        #     self.lineEdit_samp_time.setText(str(self.enc_list[0].filter_dt.get() / 100000))

        # if hasattr(self.xia, 'input_trigger'):
        #     if self.xia.input_trigger is not None:
        #         self.xia.input_trigger.unit_sel.put(1)  # ms, not us
        #         #self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_batch_mode.setXiaSampTime)
        #         self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_run.setXiaSampTime)
        #         self.lineEdit_xia_samp.setText(str(self.xia.input_trigger.period_sp.get()))
        #
        # self.dets_with_amp = [self.detector_dictionary[det]['obj'] for det in self.detector_dictionary
        #                      if self.detector_dictionary[det]['obj'].name[:3] == 'pba' and hasattr(self.detector_dictionary[det]['obj'], 'amp')]

        with open('/nsls2/xf08id/settings/json/foil_wheel.json') as fp:
            reference_foils = [item['element'] for item in json.load(fp)]
            reference_foils.append('--')

        for foil in reference_foils:
            self.comboBox_reference_foils.addItem(foil)

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
        self.figure_gen_scan.ax.grid(alpha=0.4)

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

    def process_detsig(self):
        self.comboBox_detectorssig.clear()
        for i in range(self.comboBox_detectors.count()):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'], 'dev_name'):#hasattr(list(self.detector_dictionary.keys())[i], 'dev_name'):
                if self.comboBox_detectors.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].dev_name.get():
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)
            else:
                if self.comboBox_detectors.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)

    def process_detsig_den(self):
        self.comboBox_signals_den.clear()
        for i in range(self.comboBox_gen_det_den.count() - 1):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'], 'dev_name'):#hasattr(list(self.detector_dictionary.keys())[i], 'dev_name'):
                if self.comboBox_detectors_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].dev_name.get():
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig_den.addItems(detsig)
            else:
                if self.comboBox_signals_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['device']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_channels_den.addItems(detsig)
        if self.comboBox_detectors_den.currentText() == '1':
            self.comboBox_channels_den.addItem('1')

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

    def enable_fb(self, value):
        if self.radioButton_fb_local.isChecked():
            if value == 0:
                if self.piezo_thread.go != 0 or self.fb_master != 0 or self.hhm.fb_status.get() != 0:
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
            if hasattr(self, 'piezo_thread'):
                self.piezo_thread.go = 0
            self.hhm.fb_status.put(0)
            self.fb_master = 0
            self.pushEnableHHMFeedback.setChecked(False)
        else:
            if self.fb_master:
                #print('starting piezo thread')
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

    def set_reference_foil(self):
        foil = self.comboBox_reference_foils.currentText()
        self.RE(self.aux_plan_funcs['set_reference_foil'](foil))

    def update_piezo_params(self):
        self.piezo_line = int(self.hhm.fb_line.get())
        self.piezo_center = float(self.hhm.fb_center.get())
        self.piezo_nlines = int(self.hhm.fb_nlines.get())
        self.piezo_nmeasures = int(self.hhm.fb_nmeasures.get())
        self.piezo_kp = float(self.hhm.fb_pcoeff.get())
        dlg = UpdatePiezoDialog.UpdatePiezoDialog(str(self.piezo_line), str(self.piezo_center), str(self.piezo_nlines),
                                                  str(self.piezo_nmeasures), str(self.piezo_kp), parent=self)
        if dlg.exec_():
            piezo_line, piezo_center, piezo_nlines, piezo_nmeasures, piezo_kp = dlg.getValues()
            self.piezo_line = int(round(float(piezo_line)))
            self.piezo_center = float(piezo_center)
            self.piezo_nlines = int(round(float(piezo_nlines)))
            self.piezo_nmeasures = int(round(float(piezo_nmeasures)))
            self.piezo_kp = float(piezo_kp)


            def update_piezo_params_plan(hhm, line, center, nlines,
                                         measures, pcoeff):
                yield from bps.mv(hhm.fb_line, line,
                                  hhm.fb_center, center,
                                  hhm.fb_nlines, nlines,
                                  hhm.fb_nmeasures, measures,
                                  hhm.fb_pcoeff, pcoeff)

            self.RE(update_piezo_params_plan(self.hhm,
                                             line=self.piezo_line,
                                             center=self.piezo_center,
                                             nlines=self.piezo_nlines,
                                             measures=self.piezo_nmeasures,

                                             pcoeff=self.piezo_kp))

    def change_fb_center_plan(self,hhm, center):
        yield from bps.mv(hhm.fb_center, center)

    def fb_center_increase(self):
        a = self.hhm.fb_center.get()
        #print(a)
        self.RE(self.change_fb_center_plan(self.hhm,a + 1))


    def fb_center_decrease(self):
        a = self.hhm.fb_center.get()
        #print(a)
        self.RE(self.change_fb_center_plan(self.hhm, a - 1))


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
                    coeff, var_matrix = curve_fit(gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
                    centers.append(960 - coeff[1])

            if len(centers) > 0:
                self.piezo_center = float(sum(centers) / len(centers))
                self.settings.setValue('piezo_center', self.piezo_center)
                self.hhm.fb_center.put(self.piezo_center)

    # def gauss(self, x, *p):
    #     A, mu, sigma = p
    #     return A * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2))


    def get_offsets(self):
        self.RE(self.service_plan_funcs['get_offsets']())

    def get_readouts(self):
        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.get() in adc_names]
        self.RE(self.aux_plan_funcs['get_adc_readouts'](20, *adcs, stdout = self.parent_gui.emitstream_out))



class piezo_fb_thread(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui

        P = 0.004 * self.gui.piezo_kp
        I = 0  # 0.02
        D = 0  # 0.01
        self.pid = PID(P, I, D)
        # self.sampleTime = 0.00025
        self.sampleTime = 0.001 # Denis testing on May 25, 2021
        self.pid.setSampleTime(self.sampleTime)
        self.pid.windup_guard = 3
        self.go = 0

        self.truncate_data = False

    def determine_beam_position_from_image(self, line = 420, center_point = 655, n_lines = 1):
        try:

            image = self.gui.bpm_es.image.array_data.read()['bpm_es_image_array_data']['value'].reshape((960,1280))

        except Exception as e:
            print(f"Exception: {e}\nPlease, check the max retries value in the piezo feedback IOC or maybe the network load (too many cameras).")
            return

        return determine_beam_position_from_fb_image(image, line=line, center_point=center_point, n_lines=n_lines, truncate_data=self.truncate_data)


    def gaussian_piezo_feedback(self, line = 420, center_point = 655, n_lines = 1, n_measures = 10):

        current_position = self.determine_beam_position_from_image(line = line, center_point = center_point, n_lines = n_lines)
        # print(f'current position: {current_position}')
        if current_position:
            self.pid.SetPoint = 960 - center_point
            self.pid.update(current_position)
            deviation = self.pid.output
            # deviation = -(coeff[1] - center_point)
            piezo_diff = deviation  # * 0.0855

            curr_value = self.gui.hhm.pitch.read()['hhm_pitch']['value']
            # print(f"{ttime.ctime()} curr_value: {curr_value}, piezo_diff: {piezo_diff}, delta: {curr_value - piezo_diff}")
            try:
                self.gui.hhm.pitch.move(curr_value - piezo_diff)
            except:
                print('failed to correct pitch due to controller bug (DSSI works on it)')  # TODO: Denis 5/25/2021

    def adjust_center_point(self, line=420, center_point=655, n_lines=1, n_measures=10):
        # getting center:
        centers = []
        #print(f'center_point INITIALLY is {center_point}')
        for i in range(n_measures):
            current_position = self.determine_beam_position_from_image(line=line, center_point=center_point,
                                                                       n_lines=n_lines)
            if current_position:
                centers.append(960 - current_position)
        # print('Centers: {}'.format(centers))
        # print('Old Center Point: {}'.format(center_point))
        if len(centers) > 0:
            center_point = np.mean(centers)
            print(f'center_point DETERMINED is {center_point}')
            self.gui.settings.setValue('piezo_center', center_point)
            self.gui.piezo_center = center_point
            self.gui.hhm.fb_center.put(self.gui.piezo_center)
            # print('New Center Point: {}'.format(center_point))

    def run(self):
        self.go = 1
        # self.adjust_center_point(line = self.gui.piezo_line, center_point = self.gui.piezo_center, n_lines = self.gui.piezo_nlines, n_measures = self.gui.piezo_nmeasures)

        while (self.go):
            # print("Here all the time? 1")
            if len([self.gui.shutter_dictionary[shutter] for shutter in self.gui.shutter_dictionary if
                    self.gui.shutter_dictionary[shutter].shutter_type != 'SP' and
                                    self.gui.shutter_dictionary[shutter].state.read()['{}_state'.format(shutter)][
                                        'value'] != 0]) == 0:
                self.gaussian_piezo_feedback(line=self.gui.piezo_line, center_point=self.gui.piezo_center,
                                             n_lines=self.gui.piezo_nlines, n_measures=self.gui.piezo_nmeasures)
                # print("Here all the time? 4")
                ttime.sleep(self.sampleTime)
                # print("Here all the time? 5")
            else:
                # print("Here all the time? Not here!")
                ttime.sleep(self.sampleTime)


