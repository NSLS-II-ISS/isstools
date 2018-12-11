import math
import time as ttime
from datetime import datetime

import bluesky.plan_stubs as bps
import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from bluesky.callbacks import LivePlot
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from scipy.optimize import curve_fit

from isstools.dialogs import (UpdatePiezoDialog, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure
from isstools.elements.math import gauss
from isstools.pid import PID

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_setup.ui')


class UIBeamlineSetup(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 hhm,
                 db,
                 adc_list,
                 enc_list,
                 detector_dictionary,
                 xia,
                 ic_amplifiers,
                 plan_funcs,
                 service_plan_funcs,
                 aux_plan_funcs,
                 motor_dictionary,
                 create_log_scan,
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
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.detector_dictionary = detector_dictionary
        self.xia = xia
        self.ic_amplifiers = ic_amplifiers
        self.plan_funcs = plan_funcs
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
            self.piezo_line = int(self.hhm.fb_line.value)
            self.piezo_center = float(self.hhm.fb_center.value)
            self.piezo_nlines = int(self.hhm.fb_nlines.value)
            self.piezo_nmeasures = int(self.hhm.fb_nmeasures.value)
            self.piezo_kp = float(self.hhm.fb_pcoeff.value)
            self.hhm.fb_status.subscribe(self.update_fb_status)
            self.piezo_thread = piezo_fb_thread(self) 
            self.push_update_piezo.clicked.connect(self.update_piezo_params)
            self.push_increase_center.clicked.connect(self.fb_center_increase)
            self.push_decrease_center.clicked.connect(self.fb_center_decrease)
            self.push_update_piezo_center.clicked.connect(self.update_piezo_center)
            self.push_set_reference_foil.clicked.connect(self.set_reference_foil)




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
        self.push_tune_beamline.clicked.connect(self.tune_beamline)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.det_list = [detector_dictionary[det]['obj'].dev_name.value if hasattr(detector_dictionary[det]['obj'], 'dev_name') else detector_dictionary[det]['obj'].name for det in detector_dictionary]
        self.det_sorted_list = self.det_list
        self.det_sorted_list.sort()

        self.comboBox_gen_det.addItems(self.det_sorted_list)
        self.comboBox_gen_det_den.addItem('1')
        self.comboBox_gen_det_den.addItems(self.det_sorted_list)
        self.comboBox_gen_mot.addItems(self.mot_sorted_list)
        self.comboBox_gen_det.currentIndexChanged.connect(self.process_detsig)
        self.comboBox_gen_det_den.currentIndexChanged.connect(self.process_detsig_den)
        self.process_detsig()
        self.process_detsig_den()

        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        self.pushEnableHHMFeedback.setChecked(self.hhm.fb_status.value)
        self.radioButton_fb_local.setEnabled(not self.hhm.fb_status.value)
        self.radioButton_fb_remote.setEnabled(not self.hhm.fb_status.value)
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)
        self.pushEnableHHMFeedback.toggled.connect(self.radioButton_fb_local.setDisabled)
        self.pushEnableHHMFeedback.toggled.connect(self.radioButton_fb_remote.setDisabled)


        if 'bpm_es' in self.detector_dictionary:
            self.bpm_es = self.detector_dictionary['bpm_es']['obj']



        if len(self.adc_list):
            times_arr = np.array(list(self.adc_list[0].averaging_points.enum_strs))
            times_arr[times_arr == ''] = 0.0
            times_arr = list(times_arr.astype(np.float) * self.adc_list[0].sample_rate.value / 100000)
            times_arr = [str(elem) for elem in times_arr]
            self.comboBox_samp_time.addItems(times_arr)
            #   self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_batch_mode.setAnalogSampTime)
            self.comboBox_samp_time.currentTextChanged.connect(self.parent_gui.widget_run.setAnalogSampTime)
            self.comboBox_samp_time.setCurrentIndex(self.adc_list[0].averaging_points.value)

        if len(self.enc_list):
            #self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_batch_mode.setEncSampTime)
            self.lineEdit_samp_time.textChanged.connect(self.parent_gui.widget_run.setEncSampTime)
            self.lineEdit_samp_time.setText(str(self.enc_list[0].filter_dt.value / 100000))

        if hasattr(self.xia, 'input_trigger'):
            if self.xia.input_trigger is not None:
                self.xia.input_trigger.unit_sel.put(1)  # ms, not us
                #self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_batch_mode.setXiaSampTime)
                self.lineEdit_xia_samp.textChanged.connect(self.parent_gui.widget_run.setXiaSampTime)
                self.lineEdit_xia_samp.setText(str(self.xia.input_trigger.period_sp.value))

        self.dets_with_amp = [self.detector_dictionary[det]['obj'] for det in self.detector_dictionary
                             if self.detector_dictionary[det]['obj'].name[:3] == 'pba' and hasattr(self.detector_dictionary[det]['obj'], 'amp')]



        reference_foils = ['Ti', 'V','Cr', 'Mn', 'Fe','Co', 'Ni','Cu', 'Zn','Pt', 'Au', 'Se', 'Pb', 'Nb','Mo','Ru',
                           'Rh', 'Pd','Ag','Sn','Sb', '--']

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
                if shutter.state.value:
                    ret = question_message_box(self,'Photon shutter closed', 'Proceed with the shutter closed?')
                    if not ret:
                        print('Aborted!')
                        return False
                    break

        if curr_element is not None:
            self.comboBox_gen_det.setCurrentText(curr_element['det_name'])
            self.comboBox_gen_detsig.setCurrentText(curr_element['det_sig'])
            self.comboBox_gen_det_den.setCurrentText('1')
            self.comboBox_gen_mot.setCurrentText(self.motor_dictionary[curr_element['motor_name']]['description'])
            self.edit_gen_range.setText(str(curr_element['scan_range']))
            self.edit_gen_step.setText(str(curr_element['step_size']))


        curr_det = ''
        detectors = []

        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)

        for i in range(self.comboBox_gen_det.count()):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'], 'dev_name'):
                if self.comboBox_gen_det.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detectors.append(curr_det)
            else:
                if self.comboBox_gen_det.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detectors.append(curr_det)
                if self.comboBox_gen_det_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detectors.append(curr_det)

        #curr_mot = self.motor_dictionary[self.comboBox_gen_mot.currentText()]['object']
        for motor in self.motor_dictionary:
            if self.comboBox_gen_mot.currentText() == self.motor_dictionary[motor]['description']:
                curr_mot = self.motor_dictionary[motor]['object']
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
            update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan,self.canvas_gen_scan)


        result_name = self.comboBox_gen_det.currentText()
        if self.comboBox_gen_det_den.currentText() != '1':
            result_name += '/{}'.format(self.comboBox_gen_det_den.currentText())

        print(self.comboBox_gen_detsig.currentText())
        print(self.comboBox_gen_detsig_den.currentText())
        print(result_name)
        print(curr_mot)

        self.push_gen_scan.setEnabled(False)
        try:
            uid_list = list(self.aux_plan_funcs['general_scan'](detectors, self.comboBox_gen_detsig.currentText(),
                                               self.comboBox_gen_detsig_den.currentText(),
                                               result_name, curr_mot, rel_start, rel_stop,
                                               num_steps, False,
                                               retries=1,
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

    def tune_beamline(self):
        print('[Beamline tuning] Starting...')
        self.pushEnableHHMFeedback.setChecked(False)
        #insert bpm fm
        self.detector_dictionary['bpm_fm']['obj'].insert()
        previous_detector = None
        self.RE(bps.sleep(1))

        for element in self.tune_elements:
            print('[Beamline tuning] '+ element['comment'])
            detector = self.detector_dictionary[element['detector']]['obj']
            if detector != previous_detector:
                update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan, self.canvas_gen_scan)
            detector_channel_short = self.detector_dictionary[element['detector']]['channels'][0]
            detector_channel_full = f'{detector.name}_{detector_channel_short}'
            motor = self.motor_dictionary[element['motor']]['object']
            self.RE(self.aux_plan_funcs['tuning_scan'](motor, detector, detector_channel_short,
                                                       element['range'],
                                                       element['step'],
                                                       retries=element['retries'],
                                                       stdout=self.parent_gui.emitstream_out
                                                       ),
                    LivePlot(detector_channel_full, x=motor.name, ax=self.figure_gen_scan.ax))
            # turn camera into continuous mode
            if hasattr(detector, 'image_mode'):
                self.RE(bps.mv(getattr(detector, 'image_mode'), 2))
                self.RE(bps.mv(getattr(detector, 'acquire'), 1))
            previous_detector = detector

        self.detector_dictionary['bpm_fm']['obj'].retract()
        print('[Beamline tuning] Beamline tuning complete')


    def process_detsig(self):
        self.comboBox_gen_detsig.clear()
        for i in range(self.comboBox_gen_det.count()):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'], 'dev_name'):#hasattr(list(self.detector_dictionary.keys())[i], 'dev_name'):
                if self.comboBox_gen_det.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)
            else:
                if self.comboBox_gen_det.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig.addItems(detsig)

    def process_detsig_den(self):
        self.comboBox_gen_detsig_den.clear()
        for i in range(self.comboBox_gen_det_den.count() - 1):
            if hasattr(self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'], 'dev_name'):#hasattr(list(self.detector_dictionary.keys())[i], 'dev_name'):
                if self.comboBox_gen_det_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].dev_name.value:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig_den.addItems(detsig)
            else:
                if self.comboBox_gen_det_den.currentText() == self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj'].name:
                    curr_det = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['obj']
                    detsig = self.detector_dictionary[list(self.detector_dictionary.keys())[i]]['elements']
                    self.comboBox_gen_detsig_den.addItems(detsig)
        if self.comboBox_gen_det_den.currentText() == '1':
            self.comboBox_gen_detsig_den.addItem('1')


    def adjust_gains(self):
        detectors = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        self.adjust_ic_gains_func(*detectors, stdout = self.parent_gui.emitstream_out)

    def prepare_beamline(self):
        self.RE(self.service_plan_funcs['prepare_beamline_plan'](energy=int(self.lineEdit_energy.text())))


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
            if hasattr(self, 'piezo_thread'):
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

    def set_reference_foil(self):
        foil = self.comboBox_reference_foils.currentText()
        self.RE(self.reference_foil_func(foil))

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
        print(a)
        self.RE(self.change_fb_center_plan(self.hhm,a + 1))


    def fb_center_decrease(self):
        a = self.hhm.fb_center.get()
        print(a)
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
                    coeff, var_matrix = curve_fit(self.gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
                    centers.append(960 - coeff[1])
    
            if len(centers) > 0:
                self.piezo_center = float(sum(centers) / len(centers))
                self.settings.setValue('piezo_center', self.piezo_center)
                self.hhm.fb_center.put(self.piezo_center)

    def gauss(self, x, *p):
        A, mu, sigma = p
        return A * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2))


    def get_offsets(self):
        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.value in adc_names]
        self.RE(self.service_plan_funcs['get_adc_offsets'](20, *adcs, stdout = self.parent_gui.emitstream_out))

    def get_readouts(self):
        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.value in adc_names]
        self.RE(self.aux_plan_funcs['get_adc_readouts'](20, *adcs, stdout = self.parent_gui.emitstream_out))



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
            coeff, var_matrix = curve_fit(gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
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
                coeff, var_matrix = curve_fit(gauss, list(range(960)), sum_lines, p0=[1, index_max, 5])
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


