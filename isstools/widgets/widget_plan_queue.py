import os
from subprocess import call

from isstools.widgets import widget_energy_selector


import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore, QtGui

from isstools.conversions import xray
from isstools.dialogs import UpdateAngleOffset
from isstools.elements.figure_update import update_figure
from xas.trajectory import TrajectoryCreator
from isstools.elements.figure_update import setup_figure
from ophyd import utils as ophyd_utils
from xas.bin import xas_energy_grid
from isstools.dialogs.BasicDialogs import question_message_box, message_box

from isstools.widgets import widget_emission_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_plan_queue.ui')

class UIPlanQueue(*uic.loadUiType(ui_path)):
    trajectoriesChanged = QtCore.pyqtSignal()

    def __init__(self,
                 hhm= None,
                 spectrometer=None,
                 scan_processor=None,
                 detector_dict=[],
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.hhm = hhm
        self.spectrometer = spectrometer

        self.scan_processor = scan_processor