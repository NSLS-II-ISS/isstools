import math
import time as ttime
from datetime import datetime

import bluesky.plan_stubs as bps
import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from bluesky.callbacks import LivePlot
from isstools.dialogs import (UpdatePiezoDialog, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer.ui')

class UISpectrometer(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 # hhm,
                 # db,
                 detector_dictionary,
                 motor_dictionary,
                 aux_plan_funcs,
                 # ic_amplifiers,
                 # service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 # parent_gui,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.RE = RE
        # self.db = db
        self.detector_dictionary = detector_dictionary
        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        # self.parent_gui = parent_gui
        self.last_motor_used = ''
        self.push_1D_scan.clicked.connect(self.run_scan)
        self.det_list = list(detector_dictionary.keys())
        self.comboBox_detectors.addItems(self.det_list)
        self.comboBox_detectors.currentIndexChanged.connect(self.detector_selected)
        self.detector_selected()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)

    def addCanvas(self):
        self.figure_scan = Figure()
        self.figure_scan.set_facecolor(color='#FcF9F6')
        self.canvas_scan = FigureCanvas(self.figure_scan)
        self.figure_scan.ax = self.figure_scan.add_subplot(111)
        self.toolbar_scan = NavigationToolbar(self.canvas_scan, self, coordinates=True)
        self.plot_scan.addWidget(self.toolbar_scan)
        self.plot_scan.addWidget(self.canvas_scan)
        self.canvas_scan.draw_idle()
        self.cursor_scan = Cursor(self.figure_scan.ax, useblit=True, color='green', linewidth=0.75)
        self.figure_scan.ax.grid(alpha=0.4)

    def run_scan(self, **kwargs):
        self.canvas_scan.mpl_disconnect(self.cid_scan)
        detector_name = self.comboBox_detectors.currentText()
        detector = self.detector_dictionary[detector_name]['device']
        channels = self.detector_dictionary[detector_name]['channels']
        channel = channels[self.comboBox_channels.currentIndex()]
        update_figure([self.figure_scan.ax], self.toolbar_scan,self.canvas_scan)

        motor_suffix = self.comboBox_motor.currentText().split(' ')[-1]
        motor_name = f'six_axes_stage_{motor_suffix}'
        self.motor = self.motor_dictionary[motor_name]['object']

        range= getattr(self,f'doubleSpinBox_range_{motor_suffix}').value()
        step = getattr(self, f'doubleSpinBox_step_{motor_suffix}').value()
        rel_start = -float(range) / 2
        rel_stop = float(range) / 2
        num_steps = int(round(range/ float(step))) + 1

        uid_list = self.RE(self.aux_plan_funcs['general_scan']([detector],
                                                               self.motor,
                                                               rel_start,
                                                               rel_stop,
                                                               num_steps, ),
                           LivePlot(channel,  self.motor.name, ax=self.figure_scan.ax))

        self.figure_scan.tight_layout()
        self.canvas_scan.draw_idle()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.last_motor_used = self.motor

    def run_2dscan(self, detectors, motor1, motor2):

        plan = rel_spiral_square(detectors, giantxy.x, giantxy.y, 15, 15, 15, 15)
        RE()

    def getX_scan(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.last_motor_used != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.last_motor_used,
                                                      parent=self.canvas_scan)
                if dlg.exec_():
                    pass

    def detector_selected(self):
        self.comboBox_channels.clear()
        detector = self.comboBox_detectors.currentText()
        self.comboBox_channels.addItems(self.detector_dictionary[detector]['channels'])




