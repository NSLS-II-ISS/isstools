import json
import pkg_resources
from PyQt5 import uic
from isstools.widgets import widget_emission_energy_selector
import bluesky.plan_stubs as bps
from xas.spectrometer import Crystal

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_johann_spectrometer.ui')
from xraydb import xray_line

class UIJohannTools(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None,
                 motor_dictionary=None,
                 RE=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent=parent
        self.motor_dictionary = motor_dictionary
        self.RE = RE

        self.settings = parent.parent.settings

        self.widget_emission_energy = widget_emission_energy_selector.UIEmissionEnergySelector(parent=self)
        self.layout_emission_energy.addWidget(self.widget_emission_energy)

        self.push_update_crystal_parking.clicked.connect(self.update_crystal_parking)
        self.push_park_crystal.clicked.connect(self.park_crystal)
        self.push_set_default_soft_limits.clicked.connect(self.set_default_soft_limits)
        self.push_compute_crystal_position.clicked.connect(self.compute_crystal_position)

        self.spinBox_crystal_park_x.setValue(self.settings.value('johann_crystal_park_x', defaultValue=0, type=float))
        self.spinBox_crystal_park_y.setValue(self.settings.value('johann_crystal_park_y', defaultValue=0, type=float))

        self.spinBox_bragg_angle_nom.setValue(self.settings.value('johann_bragg_angle_nom', defaultValue=0))
        self.spinBox_crystal_nom_x.setValue(self.settings.value('johann_crystal_x_nom', defaultValue=0))
        self.spinBox_crystal_nom_y.setValue(self.settings.value('johann_crystal_y_nom', defaultValue=0))
        self.spinBox_det_nom_y.setValue(self.settings.value('johann_det_nom_y', defaultValue=0))
        self.spinBox_crystal_stage_nom_x.setValue(self.settings.value('crystal_stage_nom_x', defaultValue=0))
        self.spinBox_crystal_stage_nom_y.setValue(self.settings.value('crystal_stage_nom_y', defaultValue=0))



    def update_crystal_parking(self):
        park_x = self.motor_dictionary['auxxy_x']['object'].user_readback.get()
        park_y = self.motor_dictionary['auxxy_y']['object'].user_readback.get()
        self.spinBox_crystal_park_x.setValue(park_x)
        self.spinBox_crystal_park_y.setValue(park_y)
        self.settings.setValue('johann_crystal_park_x', park_x)
        self.settings.setValue('johann_crystal_park_y', park_y)


    def park_crystal(self):
        x = self.spinBox_crystal_park_x.value()
        y = self.spinBox_crystal_park_x.value()

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
        R = float(self.edit_crystal_R.text())
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

