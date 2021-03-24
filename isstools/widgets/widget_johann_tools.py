import json
import pkg_resources
from PyQt5 import uic
from isstools.widgets import widget_emission_energy_selector
import bluesky.plan_stubs as bps
from xas.spectrometer import Crystal
import pandas as pd
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_johann_spectrometer.ui')
from xraydb import xray_line

class UIJohannTools(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None,
                 RE=None,
                 motor_dictionary=None,
                 detector_dictionary=None,
                 aux_plan_funcs=None,
                 service_plan_funcs=None,
                 embedded_run_scan_func=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent=parent
        self.motor_dictionary = motor_dictionary
        self.detector_dictionary = detector_dictionary
        self.aux_plan_funcs = aux_plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE

        self._run_any_scan = embedded_run_scan_func


        self.settings = parent.parent.settings
        self._cur_alignment_motor = None

        self.widget_emission_energy = widget_emission_energy_selector.UIEmissionEnergySelector(parent=self)
        self.layout_emission_energy.addWidget(self.widget_emission_energy)

        self.push_update_crystal_parking.clicked.connect(self.update_crystal_parking)
        self.push_park_crystal.clicked.connect(self.park_crystal)
        self.push_set_default_soft_limits.clicked.connect(self.set_default_soft_limits)
        self.push_compute_crystal_position.clicked.connect(self.compute_crystal_position)
        self.push_move_crystal.clicked.connect(self.move_crystal)
        self.comboBox_johann_tweak_motor.currentIndexChanged.connect(self.update_tweak_motor)

        self.push_tweak_down.clicked.connect(self.tweak_down)
        self.push_tweak_up.clicked.connect(self.tweak_up)

        for chan in self.detector_dictionary['Pilatus 100k']['channels']:
            self.comboBox_pilatus_channels.addItem(chan)

        self.comboBox_pilatus_channels.setCurrentIndex(self.settings.value('johann_alignment_pilatus_channel', defaultValue=0, type=int))
        self.comboBox_pilatus_channels.currentIndexChanged.connect(self.update_pilatus_channel_selection)

        self.push_scan_crystal_y.clicked.connect(self.scan_crystal_y)
        self.push_scan_energy.clicked.connect(self.scan_energy)

        self.spinBox_crystal_park_x.setValue(self.settings.value('johann_crystal_park_x', defaultValue=0, type=float))
        self.spinBox_crystal_park_y.setValue(self.settings.value('johann_crystal_park_y', defaultValue=0, type=float))

        self.spinBox_bragg_angle_nom.setValue(self.settings.value('johann_bragg_angle_nom', defaultValue=0))
        self.spinBox_crystal_nom_x.setValue(self.settings.value('johann_crystal_x_nom', defaultValue=0))
        self.spinBox_crystal_nom_y.setValue(self.settings.value('johann_crystal_y_nom', defaultValue=0))
        self.spinBox_det_nom_y.setValue(self.settings.value('johann_det_nom_y', defaultValue=0))
        self.spinBox_crystal_stage_nom_x.setValue(self.settings.value('crystal_stage_nom_x', defaultValue=0))
        self.spinBox_crystal_stage_nom_y.setValue(self.settings.value('crystal_stage_nom_y', defaultValue=0))

        self.update_tweak_motor()

        _tweak_motor_list = [self.comboBox_johann_tweak_motor.itemText(i)
                             for i in range(self.comboBox_johann_tweak_motor.count())]
        self._alignment_data = pd.DataFrame(columns=_tweak_motor_list)



    def update_crystal_parking(self):
        park_x = self.motor_dictionary['auxxy_x']['object'].user_readback.get()
        park_y = self.motor_dictionary['auxxy_y']['object'].user_readback.get()
        self.spinBox_crystal_park_x.setValue(park_x)
        self.spinBox_crystal_park_y.setValue(park_y)
        self.settings.setValue('johann_crystal_park_x', park_x)
        self.settings.setValue('johann_crystal_park_y', park_y)


    def park_crystal(self):
        x = self.spinBox_crystal_park_x.value()
        y = self.spinBox_crystal_park_y.value()

        self.RE(bps.mv(self.motor_dictionary['auxxy_x']['object'], x))
        self.RE(bps.mv(self.motor_dictionary['auxxy_y']['object'], y))


    def set_default_soft_limits(self, *, dx_hi=50, dx_lo=50, dy_hi=50, dy_lo=50):
        motor_x = self.motor_dictionary['auxxy_x']['object']
        motor_y = self.motor_dictionary['auxxy_y']['object']

        x_cur = motor_x.user_readback.get()
        y_cur = motor_y.user_readback.get()

        motor_x.high_limit_travel.put(x_cur + dx_hi)
        motor_x.low_limit_travel.put(x_cur - dx_lo)

        motor_y.high_limit_travel.put(y_cur + dy_hi)
        motor_y.low_limit_travel.put(y_cur - dy_lo)


    def compute_crystal_position(self):
        energy = float(self.widget_emission_energy.edit_E.text())
        kind = self.widget_emission_energy.comboBox_crystal_kind.currentText()
        _reflection = self.widget_emission_energy.lineEdit_reflection.text()
        hkl = [int(i) for i in _reflection[1:-1].split(',')]
        R = float(self.widget_emission_energy.edit_crystal_R.text())
        cr = Crystal(R, 100, hkl, kind)
        cr.place_E(energy)
        bragg_angle = cr.ba_deg
        cr_x = cr.x
        cr_y = cr.y
        det_y = cr.d_y
        cr_x_stage = self.spinBox_crystal_park_x.value() + (R - cr_x)
        cr_y_stage = self.spinBox_crystal_park_y.value() + cr_y

        self.spinBox_bragg_angle_nom.setValue(bragg_angle)
        self.spinBox_crystal_nom_x.setValue(cr_x)
        self.spinBox_crystal_nom_y.setValue(cr_y)
        self.spinBox_det_nom_y.setValue(det_y)

        self.spinBox_crystal_stage_nom_x.setValue(cr_x_stage)
        self.spinBox_crystal_stage_nom_y.setValue(cr_y_stage)

        self.settings.setValue('johann_bragg_angle_nom', bragg_angle)
        self.settings.setValue('johann_crystal_x_nom', cr_x)
        self.settings.setValue('johann_crystal_y_nom', cr_y)
        self.settings.setValue('johann_det_nom_y', det_y)

        self.settings.setValue('crystal_stage_nom_x', cr_x_stage)
        self.settings.setValue('crystal_stage_nom_y', cr_y_stage)


    def move_crystal(self):
        motor_x = self.motor_dictionary['auxxy_x']['object']
        motor_y = self.motor_dictionary['auxxy_y']['object']

        x = self.spinBox_crystal_stage_nom_x.value()
        y = self.spinBox_crystal_stage_nom_y.value()

        self.RE(bps.mv(motor_x, x))
        self.RE(bps.mv(motor_y, y))

    def update_tweak_motor(self):
        value = self.comboBox_johann_tweak_motor.currentText()
        if value == 'Crystal X':
            motor = self.motor_dictionary['auxxy_x']['object']
            step_size = 2.5
        elif value == 'Bender':
            motor = self.motor_dictionary['bender']['object']
            step_size = 5
        elif value == 'Crystal Z':
            motor = self.motor_dictionary['usermotor1']['object']
            step_size = 2.5

        self.doubleSpinBox_tweak_motor_step.setValue(step_size)
        pos = motor.user_readback.get()
        self.doubleSpinBox_tweak_motor_pos.setValue(pos)
        self._cur_alignment_motor = {'motor' : motor, 'name' : value}

    def update_pilatus_channel_selection(self):
        idx = self.comboBox_pilatus_channels.currentIndex()
        self.settings.setValue('johann_alignment_pilatus_channel', idx)

    def tweak_up(self):
        self._tweak(1)

    def tweak_down(self):
        self._tweak(-1)

    def _tweak(self, direction):
        motor = self._cur_alignment_motor['motor']
        step = self.doubleSpinBox_tweak_motor_step.value()
        self.RE(bps.mvr(motor, direction * step))
        pos = motor.user_readback.get()
        self.doubleSpinBox_tweak_motor_pos.setValue(pos)

    def scan_crystal_y(self):
        detector = self.detector_dictionary['Pilatus 100k']['device']
        channel = self.comboBox_pilatus_channels.currentText()
        motor = self.motor_dictionary['auxxy_y']['object']
        scan_range = self.doubleSpinBox_range_crystal_y.value()
        scan_step = self.doubleSpinBox_step_crystal_y.value()
        self._run_any_scan(detector, channel, motor, scan_range, scan_step)

    def scan_energy(self):
        detector = self.detector_dictionary['Pilatus 100k']['device']
        channel = self.comboBox_pilatus_channels.currentText()
        motor = self.motor_dictionary['hhm_energy']['object']
        scan_range = self.doubleSpinBox_range_energy.value()
        scan_step = self.doubleSpinBox_step_energy.value()
        self._run_any_scan(detector, channel, motor, scan_range, scan_step)

