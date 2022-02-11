
import json

import pkg_resources
from PyQt5 import uic

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_energy_selector.ui')


class UIEnergySelector(*uic.loadUiType(ui_path)):
    def __init__(self, emission = None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        if emission:
           json_data = open(pkg_resources.resource_filename('isstools', 'fluorescence_lines.json')).read()
        else:
            json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
            self.label_edge_line.setText('Line')

        self.elements_data = json.loads(json_data)
        self.comboBox_element.currentIndexChanged.connect(self.update_combo_edge)
        self.comboBox_edge.currentIndexChanged.connect(self.update_e0_value)

        elems = [item['symbol'] for item in self.elements_data]
        self.comboBox_element.addItems(elems)

    def update_combo_edge(self, index):
        self.comboBox_edge.clear()
        edges = [key for key in list(self.elements_data[index].keys()) if key != 'name' and key != 'symbol']
        edges.sort()
        self.comboBox_edge.addItems(edges)

    def update_e0_value(self):
        if self.comboBox_edge.count() > 0:
            energy = self.elements_data[self.comboBox_element.currentIndex()][self.comboBox_edge.currentText()]


            self.edit_E0.setText(str(int(energy)))
