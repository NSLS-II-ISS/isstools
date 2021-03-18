import json
import pkg_resources
from PyQt5 import uic
from isstools.widgets import widget_emission_energy_selector


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_johann_spectrometer.ui')
from xraydb import xray_line

class UIJohannTools(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent=parent

        self.widget_emission_energy = widget_emission_energy_selector.UIEmissionEnergySelector(parent=self)
        self.layout_emission_energy.addWidget(self.widget_emission_energy)