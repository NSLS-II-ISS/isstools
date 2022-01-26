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
import time as ttime
from isstools.widgets import widget_emission_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_plan_queue.ui')

class UIPlanQueue(*uic.loadUiType(ui_path)):
    # plansChanged = QtCore.pyqtSignal()

    def __init__(self,
                 hhm= None,
                 spectrometer=None,
                 plan_processor=None,
                 detector_dict=[],
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.hhm = hhm
        self.spectrometer = spectrometer

        self.plan_processor = plan_processor

        self.handle_execution_buttons_and_status()
        self.plan_processor.plan_list_update_signal.connect(self.update_plan_list)
        self.listWidget_plan_queue.itemSelectionChanged.connect(self.show_plan_parameters)
        self.plan_processor.status_update_signal.connect(self.handle_execution_buttons_and_status)

        self.pushButton_run_queue.clicked.connect(self.run_queue)
        self.pushButton_pause_queue.toggled.connect(self.pause_queue)
        self.pushButton_clear_queue.clicked.connect(self.clear_queue)


    def update_plan_list(self):
        self.listWidget_plan_queue.clear()
        for i, plan in enumerate(self.plan_processor.plan_list):
            item_str = f"{i} - {plan['plan_info']['plan_description']}"
            plan_status = plan['plan_status']
            item = QtWidgets.QListWidgetItem(item_str)
            if plan_status == 'paused':
                item.setForeground(QtGui.QColor('red'))
            elif plan_status == 'executing':
                item.setForeground(QtGui.QColor('green'))
            self.listWidget_plan_queue.addItem(item)

    def show_plan_parameters(self):
        self.listWidget_plan_properties.clear()

        plan_name = self.listWidget_plan_queue.currentItem().text()
        plan_index = self.listWidget_plan_queue.currentIndex().row()
        self.label_plan_parameters.setText(f'Parameters for {plan_name}')

        plan_kwargs = self.plan_processor.plan_list[plan_index]['plan_info']['plan_kwargs']
        for key, arg in plan_kwargs.items():
            item_str = f"{key}: {arg}"
            item = QtWidgets.QListWidgetItem(item_str)
            self.listWidget_plan_properties.addItem(item)

    def handle_execution_buttons_and_status(self):
        self.pushButton_pause_queue.setChecked(False)
        if self.plan_processor.status == 'idle':
            self.pushButton_run_queue.setEnabled(True)
            self.pushButton_pause_queue.setEnabled(False)

            self.label_plan_processor_status_indicator.setStyleSheet('background-color: rgb(0,94,0)')
            self.label_plan_processor_status_text.setText('Idle')
            self.label_plan_processor_current_plan.setText(f'Current plan:')

        elif self.plan_processor.status == 'running':
            self.pushButton_run_queue.setEnabled(False)
            self.pushButton_pause_queue.setEnabled(True)

            self.label_plan_processor_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
            self.label_plan_processor_status_text.setText('Running')
            top_item = self.listWidget_plan_queue.item(0)
            top_item.setForeground(QtGui.QColor('green'))
            self.label_plan_processor_current_plan.setText(f'Current plan: {top_item.text()}')

    def run_queue(self):
        self.plan_processor.run()

    def pause_queue(self, state):
        if state:
            self.plan_processor.pause_plan_list()
        else:
            self.plan_processor.unpause_plan_list()

    def clear_queue(self):
        self.plan_processor.clear_plan_list()

