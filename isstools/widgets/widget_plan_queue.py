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
    # plansChanged = QtCore.pyqtSignal()

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

        self.scan_processor.plan_list_update_signal.connect(self.update_plan_list)
        self.scan_processor.status_update_signal.connect(self.update_scan_processor_status)

        self.pushButton_run_queue.clicked.connect(self.run_queue)
        self.pushButton_pause_queue.clicked.connect(self.pause_queue)
        self.pushButton_resume_queue.clicked.connect(self.resume_queue)
        self.pushButton_clear_queue.clicked.connect(self.clear_queue)


    def update_plan_list(self):
        self.listWidget_plan_queue.clear()
        for plan in self.scan_processor.plan_list:
            plan_description = plan['plan_info']['plan_description']
            plan_status = plan['status']
            item = QtWidgets.QListWidgetItem(plan_description)
            if plan_status == 'paused':
                item.setForeground(QtGui.QColor('red'))
            self.listWidget_plan_queue.addItem(item)

    def update_scan_processor_status(self):
        pass

    def run_queue(self):
        self.scan_processor.run()

    def pause_queue(self):
        self.scan_processor.pause_plan_list()

    def resume_queue(self):
        self.scan_processor.resume_plan_list()

    def clear_queue(self):
        self.scan_processor.clear_plan_list()

