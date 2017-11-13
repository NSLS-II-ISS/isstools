
import json
import pkg_resources
from PyQt5 import uic

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_energy_selector.ui')


class UIEnergySelector(*uic.loadUiType(ui_path)):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        self.elements_data = json.loads(json_data)
        self.comboBox_element.currentIndexChanged.connect(self.update_combo_edge)
        self.comboBox_edge.currentIndexChanged.connect(self.update_e0_value)

        elems = [item['name'] for item in self.elements_data]
        for i in range(21, 109):
            elems[i - 21] = '{} ({:3d})'.format(elems[i - 21],i)
        self.comboBox_element.addItems(elems)

    def update_combo_edge(self, index):
        self.comboBox_edge.clear()
        edges = [key for key in list(self.elements_data[index].keys()) if key != 'name' and key != 'symbol']
        edges.sort()
        self.comboBox_edge.addItems(edges)

    def update_e0_value(self):
        if self.comboBox_edge.count() > 0:
            self.edit_E0.setText(
                str(self.elements_data[self.comboBox_element.currentIndex()][self.comboBox_edge.currentText()]))
