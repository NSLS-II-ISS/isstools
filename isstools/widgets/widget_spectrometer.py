import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from PyQt5.Qt import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np

from isstools.dialogs import MoveMotorDialog
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
from isstools.elements.transformations import  range_step_2_start_stop_nsteps
from isstools.widgets import widget_johann_tools
from xas.spectrometer import analyze_elastic_scan
from ..elements.liveplots import XASPlot, NormPlot#, XASPlotX
from ..elements.elements import get_spectrometer_line_dict
# from isstools.elements.liveplots import NormPlot
from isstools.widgets import widget_emission_energy_selector
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer.ui')

class UISpectrometer(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 plan_processor,
                 hhm,
                 db,
                 johann_emission,
                 detector_dictionary,
                 motor_dictionary,
                 shutter_dictionary,
                 aux_plan_funcs,
                 # ic_amplifiers,
                 service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.plan_processor = plan_processor
        self.plan_processor.status_update_signal.connect(self.handle_gui_elements)

        self.db = db

        self.johann_emission = johann_emission

        self.detector_dictionary = detector_dictionary
        # self.pilatus = detector_dictionary['Pilatus 100k']['device']
        self.parent = parent

        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        self.shutter_dictionary = shutter_dictionary
        self.service_plan_funcs = service_plan_funcs

        # self.element_data_spectroscopy = get_spectrometer_line_dict()

        # self.parent_gui = parent_gui
        self.last_motor_used = None
        self.push_pcl_1D_scan.clicked.connect(self.run_pcl_scan)
        # self.push_xy_scan.clicked.connect(self.run_2d_pcl_scan)
        # self.push_py_scan.clicked.connect(self.run_2d_pcl_scan)
        # self.push_gen_scan.clicked.connect(self.run_gen_scan)
        # self.push_time_scan.clicked.connect(self.run_time_scan)
        # self.push_single_shot.clicked.connect(self.single_shot)

        self.det_list = list(detector_dictionary.keys())
        self.comboBox_pcl_detectors.addItems(self.det_list)
        self.comboBox_pcl_detectors.setCurrentIndex(3) # make it PIPS by default!
        self.comboBox_pcl_detectors.currentIndexChanged.connect(self.pcl_detector_selected)
        self.pcl_detector_selected()

        # self.comboBox_gen_detectors.addItems(self.det_list)
        # self.comboBox_gen_detectors.setCurrentIndex(7) # make it Pilatus by default!
        # self.comboBox_gen_detectors.currentIndexChanged.connect(self.gen_detector_selected)
        # self.gen_detector_selected()

        self.comboBox_pcl_detectors.addItems(self.det_list)

        self.motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary
                         if ('group' in  self.motor_dictionary[motor].keys())
                         and (self.motor_dictionary[motor]['group']=='spectrometer')]

        # self.comboBox_gen_motors.addItems(self.motor_list)

        self.figure_scan, self.canvas_scan, self.toolbar_scan = setup_figure(self, self.layout_plot_scan)
        self.figure_proc, self.canvas_proc, self.toolbar_proc = setup_figure(self, self.layout_plot_processed)
        # self.figure_integ, self.canvas_integ,self.toolbar_integ = setup_figure(self, self.layout_plot_integ)

        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.cid_proc = self.canvas_proc.mpl_connect('button_press_event', self.getX_proc)
        # self.spinBox_image_max.valueChanged.connect(self.rescale_image)
        # self.spinBox_image_min.valueChanged.connect(self.rescale_image)


        self.widget_johann_tools = widget_johann_tools.UIJohannTools(parent=self,
                                                                     motor_dictionary=motor_dictionary,
                                                                     db=db,
                                                                     RE=RE,
                                                                     plan_processor=plan_processor,
                                                                     hhm=hhm,
                                                                     johann_emission=johann_emission,
                                                                     detector_dictionary=detector_dictionary,
                                                                     aux_plan_funcs=aux_plan_funcs,
                                                                     service_plan_funcs=service_plan_funcs,
                                                                     embedded_run_scan_func=self._run_any_scan,
                                                                     figure_proc=self.figure_proc,
                                                                     canvas_proc=self.canvas_proc,
                                                                     toolbar_proc=self.toolbar_proc)
        self.layout_johann_tools.addWidget(self.widget_johann_tools)


        # johann functions/subscriptions
        self._prepare_johann_elements()

        self.push_johann_update_crystal_parking.clicked.connect(self.johann_update_crystal_parking)
        self.push_update_detector_parking.clicked.connect(self.johann_update_detector_parking)
        self.push_johann_home_crystals.clicked.connect(self.johann_home_crystals)

        self.comboBox_johann_crystal.currentIndexChanged.connect(self.johann_populate_crystal_parking)

        self.update_enabled_crystals_checkboxes()

        self.checkBox_enable_main.toggled.connect(self.enable_crystal)
        self.checkBox_enable_aux2.toggled.connect(self.enable_crystal)
        self.checkBox_enable_aux3.toggled.connect(self.enable_crystal)
        self.checkBox_enable_aux4.toggled.connect(self.enable_crystal)
        self.checkBox_enable_aux5.toggled.connect(self.enable_crystal)

        self.widget_johann_line_selector = widget_emission_energy_selector.UIEmissionLineSelectorEnergyOnly(parent=self, emin=4500)
        self.layout_johann_emission_line_selector.addWidget(self.widget_johann_line_selector)
        self.comboBox_johann_roll_offset.addItems([str(i) for i in self.johann_emission.allowed_roll_offsets])
        self.push_johann_compute_geometry.clicked.connect(self.johann_compute_geometry)
        self.push_johann_move_motors.clicked.connect(self.johann_move_motors)

        self.johann_motor_list = [motor_dictionary[motor]['description'] for motor in motor_dictionary
                                    if ('group' in self.motor_dictionary[motor].keys()) and
                                        (self.motor_dictionary[motor]['group'] == 'spectrometer') and
                                        ('spectrometer_kind' in self.motor_dictionary[motor].keys()) and
                                        (self.motor_dictionary[motor]['spectrometer_kind'] == 'johann')]

        self.comboBox_johann_tweak_motor.addItems(self.johann_motor_list)
        self.johann_update_tweak_motor()
        self.comboBox_johann_tweak_motor.currentIndexChanged.connect(self.johann_update_tweak_motor)

        self.comboBox_johann_scan_motor.addItems(self.johann_motor_list)
        # self.comboBox_johann_pilatus_channels.addItems(self.detector_dictionary['Pilatus 100k']['channels'])

        self.push_johann_tweak_down.clicked.connect(self.johann_tweak_down)
        self.push_johann_tweak_up.clicked.connect(self.johann_tweak_up)


# general handling of gui elements, plotting, and scanning


    def handle_gui_elements(self):
        if self.plan_processor.status == 'idle':
            self.figure_scan.tight_layout()
            self.canvas_scan.draw_idle()
            self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
            self.liveplot_kwargs = {}
        elif self.plan_processor.status == 'running':
            self.canvas_scan.mpl_disconnect(self.cid_scan)

    def make_liveplot_func(self, plan_name, plan_kwargs):
        self.start_gen_scan_figure()
        liveplot_list = []
        try:
            liveplot_kwargs = plan_kwargs['liveplot_kwargs']
            _norm_plot = NormPlot(liveplot_kwargs['channel'],
                                  liveplot_kwargs['channel_den'],
                                  liveplot_kwargs['result_name'],
                                  liveplot_kwargs['curr_mot_name'], ax=self.figure_scan.ax)
            liveplot_list.append(_norm_plot)
            # when the liveplot is created, we also update the canvas motor:
            self._set_canvas_motor_from_name(liveplot_kwargs['curr_mot_name'])
        except:
            print(f'could not make liveplot for scan {plan_name}')
        return liveplot_list

    def _set_canvas_motor_from_name(self, motor_name):
        for motor_key, motor_dict in self.motor_dictionary.items():
            if motor_name == motor_dict['object'].name:
                self.canvas_scan.motor = motor_dict['object']

    def start_gen_scan_figure(self):
        update_figure([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan)

    def _run_any_scan(self, detectors, liveplot_det_kwargs,
                      motor, liveplot_mot_kwargs,
                      scan_range, scan_step, exposure_time=1):

        rel_start, rel_stop, num_steps =  range_step_2_start_stop_nsteps(scan_range, scan_step)

        plan_name = 'general_scan'
        plan_kwargs = {'detectors' : detectors,
                       'motor' : motor,
                       'rel_start' : rel_start,
                       'rel_stop' : rel_stop,
                       'num_steps' : num_steps,
                       'exposure_time': exposure_time,
                       'liveplot_kwargs' : {**liveplot_det_kwargs, **liveplot_mot_kwargs},
                       'tab' : 'spectrometer'}

        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)


    def getX_scan(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.canvas_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_scan.motor,
                                                          parent=self.canvas_scan)
                if dlg.exec_():
                    pass

    def _detector_selected(self, cb_det, cb_chan):
        cb_chan.clear()
        detector_name = cb_det.currentText()
        cb_chan.addItems(self.detector_dictionary[detector_name]['channels'])

# General / PCL scans

    def run_pcl_scan(self, **kwargs):
        detector = self.comboBox_pcl_detectors.currentText()
        channel = self.comboBox_pcl_channels.currentText()
        liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}

        motor_suffix = self.comboBox_pcl_motors.currentText().split(' ')[-1]
        motor = f'six_axes_stage_{motor_suffix}'
        liveplot_mot_kwargs = {'curr_mot_name': motor_name}


        scan_range = getattr(self, f'doubleSpinBox_range_pcl_{motor_suffix}').value()
        scan_step = getattr(self, f'doubleSpinBox_step_pcl_{motor_suffix}').value()
        exposure_time = self.doubleSpinBox_pcl_exposure_time.value()

        self._run_any_scan(detector, liveplot_det_kwargs,
                           motor, liveplot_mot_kwargs,
                           scan_range, scan_step, exposure_time)

        # uid_list = self._run_any_scan(detector, channel, motor, scan_range, scan_step)

    # def run_2d_pcl_scan(self):
    #     self.figure_scan.ax.set_aspect('auto')
    #     sender = QObject()
    #     sender_object = sender.sender().objectName()
    #     if 'xy' in sender_object:
    #         m1 = 'x'
    #         m2 = 'y'
    #     elif 'py' in sender_object:
    #         m1 = 'pitch'
    #         m2 = 'yaw'
    #
    #     self.canvas_scan.mpl_disconnect(self.cid_scan)
    #     detector_name = self.comboBox_pcl_detectors.currentText()
    #     detector = self.detector_dictionary[detector_name]['device']
    #     channels = self.detector_dictionary[detector_name]['channels']
    #     channel = channels[self.comboBox_pcl_channels.currentIndex()]
    #
    #     motor1 = self.motor_dictionary[f'six_axes_stage_{m1}']['object']
    #     motor2 = self.motor_dictionary[f'six_axes_stage_{m2}']['object']
    #     m1_pos = motor1.read()[motor1.name]['value']
    #     m2_pos = motor2.read()[motor2.name]['value']
    #
    #     motor1_range = getattr(self, f'doubleSpinBox_range_{m1}').value()
    #     motor2_range = getattr(self, f'doubleSpinBox_range_{m2}').value()
    #
    #     motor1_step = getattr(self, f'doubleSpinBox_step_{m1}').value()
    #     motor2_step = getattr(self, f'doubleSpinBox_step_{m2}').value()
    #
    #     motor1_nsteps = int(round(motor1_range / float(motor1_step))) + 1
    #     motor2_nsteps = int(round(motor2_range / float(motor2_step))) + 1
    #
    #     #self.figure_scan.clf()
    #     update_figure_with_colorbar([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan,self.figure_scan)
    #
    #     plan = self.aux_plan_funcs['general_spiral_scan']([detector],
    #                                                       motor1=motor1, motor2=motor2,
    #                                                       motor1_range=motor1_range, motor2_range=motor2_range,
    #                                                       motor1_nsteps=motor1_nsteps, motor2_nsteps=motor2_nsteps)
    #
    #     # xlim =
    #
    #     live_scatter = LiveScatter(motor1.name, motor2.name, channel, ax=self.figure_scan.ax,
    #                                xlim=(m1_pos - motor1_range / 2, m1_pos + motor1_range / 2),
    #                                ylim=(m2_pos - motor2_range / 2, m2_pos + motor2_range / 2),
    #                                **{'s' : 100, 'marker' : 's','cmap': 'nipy_spectral'})
    #     # live_scatter = LivePlot(channel, self.motor.name, ax=self.figure_scan.ax)
    #
    #     uid = self.RE(plan, live_scatter)
    #     self.figure_scan.ax.set_aspect('auto')
    #     self.figure_scan.tight_layout()
    #     self.canvas_scan.draw_idle()
    #     self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
    #     self.last_motor_used = [motor1, motor2]


    # def run_gen_scan(self):
    #
    #     detector_name = self.comboBox_gen_detectors.currentText()
    #     detector = self.detector_dictionary[detector_name]['device']
    #     channels = self.detector_dictionary[detector_name]['channels']
    #     channel = channels[self.comboBox_gen_channels.currentIndex()]
    #
    #     motor_name = self.comboBox_gen_motors.currentText()
    #     for k in self.motor_dictionary.keys():
    #         if self.motor_dictionary[k]['description'] == motor_name:
    #             motor = self.motor_dictionary[k]['object']
    #             break
    #
    #     scan_range = self.doubleSpinBox_gen_motor_range.value()
    #     scan_step = self.doubleSpinBox_gen_motor_step.value()
    #
    #     uid_list = self._run_any_scan(detector, channel, motor, scan_range, scan_step)


    # def run_time_scan(self):
    #     self.canvas_scan.mpl_disconnect(self.cid_scan)
    #     update_figure([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan)
    #     self.figure_scan.ax.set_aspect('auto')
    #
    #     nframes = int(self.doubleSpinBox_nframes.value())
    #
    #     lp = XASPlot('pil100k_stats1_total', 'apb_ave_ch1_mean', 'normalized I', 'time',
    #                  log=False, ax=self.figure_scan.ax, color='k', legend_keys=['I'])
    #     plan = self.service_plan_funcs['n_pil100k_exposures_plan'](nframes)
    #     self.RE(plan, lp)
    #
    #     self.figure_scan.tight_layout()
    #     self.canvas_scan.draw_idle()
    #     self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
    #     self.last_motor_used = None

    def pcl_detector_selected(self):
        self._detector_selected(self.comboBox_pcl_detectors, self.comboBox_pcl_channels)

    # def gen_detector_selected(self):
    #     self._detector_selected(self.comboBox_gen_detectors, self.comboBox_gen_channels)


    def getX_proc(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.widget_johann_tools._cur_alignment_motor:
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata,
                                                      motor=self.widget_johann_tools._cur_alignment_motor,
                                                      parent=self.canvas_proc)
                if dlg.exec_():
                    pass



    def update_scan_figure_for_energy_scan(self, E, I_fit_raw):
        # managing figures
        self.canvas_scan.mpl_disconnect(self.cid_scan)

        self.figure_scan.ax.plot(E, I_fit_raw, 'r-')

        # managing figures

        self.figure_scan.tight_layout()
        self.canvas_scan.draw_idle()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)


    def update_proc_figure(self, x_key):
        # managing figures
        self.canvas_proc.mpl_disconnect(self.cid_proc)
        if x_key == 'calibration':
            update_figure([self.figure_proc.ax], self.toolbar_proc, self.canvas_proc)
            data = self.widget_johann_tools._calibration_data
            energy_nom = data['energy_nom'].values
            energy_act = data['energy_act'].values
            energy_error = energy_act - energy_nom
            resolution = data['resolution'].values
            ax = self.figure_proc.ax
            ax.plot(energy_nom, energy_error, 'k.-')
            ax.set_xlabel('nominal energy, eV')
            ax.set_ylabel('energy error, eV')
            ax2 = self.figure_proc.ax.twinx()
            ax2.plot(energy_nom, resolution, 'rs-')
            ax2.set_ylabel('resolution, eV', color='r')
            ax.set_xlim(energy_nom.min() - 10, energy_nom.max() + 10)

        else:
            motor_pos = self.widget_johann_tools._alignment_data[x_key].values
            fwhm = self.widget_johann_tools._alignment_data['fwhm'].values
            ecen = self.widget_johann_tools._alignment_data['ecen'].values
            res = np.sqrt(fwhm**2 - (1.3e-4 * ecen)**2)

            for each_pos, each_fwhm, each_res in zip(motor_pos, fwhm, res):
                self.figure_proc.ax.plot(each_pos, each_fwhm, 'o')
                self.figure_proc.ax.plot(each_pos, each_res, '+')

            self.figure_proc.ax.set_ylabel('FWHM/resolution, eV')
            self.figure_proc.ax.set_xlabel(x_key)

        self.figure_proc.tight_layout()
        self.canvas_proc.draw_idle()
        self.cid_proc = self.canvas_proc.mpl_connect('button_press_event', self.getX_proc)


# handling Johann spectrometer elements

    def _prepare_johann_elements(self):
        self.johann_crystals_dict = {'Main': {'set_crystal_parking_func': self.johann_emission.set_main_crystal_parking,
                                              'read_crystal_parking_func': self.johann_emission.read_main_crystal_parking},
                                     'Aux2': {'set_crystal_parking_func': self.johann_emission.set_aux2_crystal_parking,
                                              'read_crystal_parking_func': self.johann_emission.read_aux2_crystal_parking},
                                     'Aux3': {'set_crystal_parking_func': self.johann_emission.set_aux3_crystal_parking,
                                              'read_crystal_parking_func': self.johann_emission.read_aux3_crystal_parking}}

        self.comboBox_johann_crystal.addItems(self.johann_crystals_dict.keys())
        self.johann_populate_crystal_parking()
        self.johann_populate_detector_parking()



    def johann_populate_crystal_parking(self):
        crystal_key = self.comboBox_johann_crystal.currentText()
        read_parking_func = self.johann_crystals_dict[crystal_key]['read_crystal_parking_func']
        x, y, roll, yaw = read_parking_func()
        self.spinBox_johann_park_x_crystal.setValue(x)
        self.spinBox_johann_park_y_crystal.setValue(y)
        self.spinBox_johann_park_roll_crystal.setValue(roll)
        self.spinBox_johann_park_yaw_crystal.setValue(yaw)

    def johann_populate_detector_parking(self):
        x, th1, th2 = self.johann_emission.read_det_arm_parking()
        self.spinBox_johann_park_x_detector.setValue(x)
        self.spinBox_johann_park_th1_detector.setValue(th1)
        self.spinBox_johann_park_th2_detector.setValue(th2)

    def johann_update_crystal_parking(self):
        ret = question_message_box(self, 'Warning',
                                   'Crystal parking update must be done at bragg angle set to 90 degrees!\n' \
                                   'Are you sure you want to proceed?')
        if ret:
            crystal_key = self.comboBox_johann_crystal.currentText()
            set_parking_func = self.johann_crystals_dict[crystal_key]['set_crystal_parking_func']
            set_parking_func()
            self.johann_populate_crystal_parking()

    def johann_update_detector_parking(self):
        ret = question_message_box(self, 'Warning',
                                   'Detector parking update must be done with great care!' \
                                   'Detector parking update must be done with detector at bragg angle set to 90 degrees!\n' \
                                   'Are you sure you want to proceed?')
        if ret:
            self.johann_emission.set_det_arm_parking()
            self.johann_populate_detector_parking()

    def johann_home_crystals(self):
        self.johann_emission.home_crystal_piezos()

    def update_enabled_crystals_checkboxes(self):
        for crystal_key, enable in self.johann_emission.enabled_crystals.items():
            checkBox_widget = getattr(self, f'checkBox_enable_{crystal_key}') # oh boy
            checkBox_widget.setChecked(enable)

    def enable_crystal(self, enable):
        sender_object = QObject().sender()
        crystal_key = sender_object.text()
        self.johann_emission.enable_crystal(crystal_key, enable)


    def _johann_update_crystal_config(self):
        crystal = self.comboBox_johann_crystal_kind.currentText()
        R = float(self.edit_johann_crystal_R.text())
        hkl = self.lineEdit_johann_hkl.text()
        hkl = hkl.replace(')', '').replace('(', '').replace(']', '').replace('[', '')
        hkl = [int(i) for i in hkl.split(',')]
        self.johann_emission.set_crystal(crystal)
        self.johann_emission.set_hkl(hkl)

    def johann_compute_geometry(self):
        self._johann_update_crystal_config()
        energy = float(self.widget_johann_line_selector.edit_E.text())
        bragg = self.johann_emission.e2bragg(energy)
        roll_offset = self.johann_emission.suggest_roll_offset(bragg)
        reflectivity = self.johann_emission.e2reflectivity(energy)

        self.lineEdit_johann_bragg.setText(f'{bragg:0.2f}')
        self.lineEdit_johann_reflectivity.setText(f'{reflectivity:0.2f}')

        for i in range(self.comboBox_johann_roll_offset.count()):
            if roll_offset == float(self.comboBox_johann_roll_offset.itemText(i)):
                self.comboBox_johann_roll_offset.setCurrentIndex(i)
                break

    def johann_move_motors(self):
        roll_offset = float(self.comboBox_johann_roll_offset.currentText())
        self.johann_emission.set_R(R)
        self.johann_emission.set_roll_offset(roll_offset) # this will compute all the motor positions and will save the config to settings

        # energy = float(self.widget_johann_line_selector.edit_E.text())
        # self.johann_emission.move(emission=energy)

    def johann_update_tweak_motor(self):
        motor_description = self.comboBox_johann_tweak_motor.currentText()

        for key, motor_dict in self.motor_dictionary.items():
            if motor_description == motor_dict['description']:
                motor_object = motor_dict['object']
                motor_step = motor_dict['typical_step']
                break

        self.doubleSpinBox_johann_tweak_motor_step.setValue(motor_step)
        pos = motor_object.user_readback.get()
        self.doubleSpinBox_johann_tweak_motor_pos.setValue(pos)
        self._cur_alignment_motor = motor_object

    def johann_tweak_up(self):
        self._johann_tweak(1)

    def johann_tweak_down(self):
        self._johann_tweak(-1)

    def _johann_tweak(self, direction):
        motor = self._cur_alignment_motor
        step = self.doubleSpinBox_johann_tweak_motor_pos.value()
        motor.move(motor.pos + direction * step, wait=True)
        pos = motor.user_readback.get()
        self.doubleSpinBox_johann_tweak_motor_pos.setValue(pos)