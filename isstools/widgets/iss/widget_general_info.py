from PyQt5 import uic, QtGui, QtCore
import pkg_resources

import isstools.widgets.widget_general_info as widget_general_info

ui_path = pkg_resources.resource_filename("isstools", "ui/ui_general_info_iss.ui")


class UIGeneralInfo(*uic.loadUiType(ui_path), widget_general_info.UIGeneralInfo):
    def __init__(
        self, *args, **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.comboBox_set_i0_gain.currentIndexChanged.connect(self.set_i0_gain)
        self.comboBox_set_it_gain.currentIndexChanged.connect(self.set_it_gain)
        self.comboBox_set_ir_gain.currentIndexChanged.connect(self.set_ir_gain)
        self.comboBox_set_if_gain.currentIndexChanged.connect(self.set_if_gain)

    def set_i0_gain(self):
        self.ic_amplifiers["i0_amp"].set_gain(
            int(self.comboBox_set_i0_gain.currentText()), 0
        )

    def set_it_gain(self):
        self.ic_amplifiers["it_amp"].set_gain(
            int(self.comboBox_set_it_gain.currentText()), 0
        )

    def set_ir_gain(self):
        self.ic_amplifiers["ir_amp"].set_gain(
            int(self.comboBox_set_ir_gain.currentText()), 0
        )

    def set_if_gain(self):
        self.ic_amplifiers["iff_amp"].set_gain(
            int(self.comboBox_set_if_gain.currentText()), 0
        )
