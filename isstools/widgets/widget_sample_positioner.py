import json
import pkg_resources
from PyQt5 import uic
from isstools.elements.elements import elements_lines_dict

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_positioner.ui')
from xraydb import xray_line
import bluesky.plan_stubs as bps


class UISamplePositioner(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None, settings=None, RE=None, sample_positioner=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.settings = settings
        self.RE = RE
        self.sample_positioner = sample_positioner

        self.push_move_to_sample.clicked.connect(self.move_to_sample)


        self.spinBox_index_stack.setValue(self.settings.value('index_stack', defaultValue=1, type=int))
        self.spinBox_index_holder.setValue(self.settings.value('index_holder', defaultValue=1, type=int))
        self.spinBox_index_sample.setValue(self.settings.value('index_sample', defaultValue=1, type=int))


    def move_to_sample(self):
        self._save_sample_index_settings()
        index_stack = self.spinBox_index_stack.value()
        index_holder = self.spinBox_index_holder.value()
        index_sample = self.spinBox_index_sample.value()
        self.sample_positioner.goto_sample(index_stack, index_holder, index_sample)
        self.RE(bps.sleep(0.1))


    def _save_sample_index_settings(self):
        self.settings.setValue('index_stack', self.spinBox_index_stack.value())
        self.settings.setValue('index_holder', self.spinBox_index_holder.value())
        self.settings.setValue('index_sample', self.spinBox_index_sample.value())


