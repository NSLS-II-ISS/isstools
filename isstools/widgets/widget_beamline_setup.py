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

        self.pushEnableHHMFeedback.setChecked(self.hhm.fb_status.value)
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)



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

    def run_gen_scan(self):
        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)
        detectors = []
        detector_name = self.comboBox_detectors.currentText()
        detector = self.detector_dictionary[detector_name]['device']
        detectors.append(detector)
        channel = self.detector_dictionary[detector_name]['channels']
        result_name = channel

        detector_name_den = self.comboBox_detectors_den.currentText()
        if detector_name_den != '1':
            detector_den = self.detector_dictionary[detector_name_den]['device']
            channel_den = self.detector_dictionary[detector_name_den]['channels']
            detectors.append(detector_den)
            result_name += '/{}'.channel_den
        else:
            channel_den = '1'


        for motor in self.motor_dictionary:
            if self.comboBox_motors.currentText() == self.motor_dictionary[motor]['description']:
                curr_mot = self.motor_dictionary[motor]['object']
                self.canvas_gen_scan.motor = curr_mot
                break



        rel_start = -float(self.edit_gen_range.text()) / 2
        rel_stop = float(self.edit_gen_range.text()) / 2
        num_steps = int(round(float(self.edit_gen_range.text()) / float(self.edit_gen_step.text()))) + 1

        update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan,self.canvas_gen_scan)

        self.push_gen_scan.setEnabled(False)
        uid_list = list(self.aux_plan_funcs['general_scan'](detectors, channel,
                                               channel_den,
                                               result_name, curr_mot, rel_start, rel_stop,
                                               num_steps,    ax=self.figure_gen_scan.ax))
        # except Exception as exc:
        #     print('[General Scan] Aborted! Exception: {}'.format(exc))
        #     print('[General Scan] Limit switch reached . Set narrower range and try again.')
        #     uid_list = []

        self.figure_gen_scan.tight_layout()
        self.canvas_gen_scan.draw_idle()
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)

        self.push_gen_scan.setEnabled(True)
        self.last_gen_scan_uid = self.db[-1]['start']['uid']
        self.push_gen_scan_save.setEnabled(True)

    def save_gen_scan(self):
        run = self.db[self.last_gen_scan_uid]
        self.user_directory = '/nlsl2/xf08id/users/{}/{}/{}/' \
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
        self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)
        self.canvas_gen_scan.motor = ''
        print(f'[Beamline tuning] Starting...', file=self.parent_gui.emitstream_out, flush=True )
        self.pushEnableHHMFeedback.setChecked(False)
        self.RE(bps.mv(self.detector_dictionary['bpm_fm']['obj'],'insert'))
        previous_detector = ''
        previous_motor = ''
        self.RE(bps.sleep(1))


        for element in self.tune_elements:
            print(f'[Beamline tuning] {element["comment"]}')
            detector = self.detector_dictionary[element['detector']]['obj']
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

        self.RE(bps.mv(self.detector_dictionary['bpm_fm']['obj'], 'retract'))
        print('[Beamline tuning] Beamline tuning complete',file=self.parent_gui.emitstream_out, flush=True)


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

    def prepare_beamline(self):
        self.RE(self.service_plan_funcs['prepare_beamline_plan'](energy=int(self.lineEdit_energy.text()),
                                                                 stdout = self.parent_gui.emitstream_out))

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
        self.RE(self.aux_plan_funcs['set_reference_foil'](foil))

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
        self.pid = PID(P, I, D)
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
            if len([self.gui.shutter_dictionary[shutter] for shutter in self.gui.shutter_dictionary if
                    self.gui.shutter_dictionary[shutter].shutter_type != 'SP' and
                                    self.gui.shutter_dictionary[shutter].state.read()['{}_state'.format(shutter)][
                                        'value'] != 0]) == 0:
                self.gaussian_piezo_feedback(line=self.gui.piezo_line, center_point=self.gui.piezo_center,
                                             n_lines=self.gui.piezo_nlines, n_measures=self.gui.piezo_nmeasures)
                #print("Here all the time? 4")
                ttime.sleep(self.sampleTime)
                #print("Here all the time? 5")
            else:
                #print("Here all the time? Not here!")
                ttime.sleep(self.sampleTime)


