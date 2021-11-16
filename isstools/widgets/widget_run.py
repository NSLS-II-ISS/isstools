import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from xas.xray import generate_energy_grid

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure

from bluesky.callbacks import LivePlot

from ..elements.liveplots import XASPlot#, XASPlotX

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')



class UIRun(*uic.loadUiType(ui_path)):
    def __init__(self,
                 scan_manager = None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.scan_manager = scan_manager
        self.push_run_scan.clicked.connect(self.run_scan)
        self.push_run_test_scan.clicked.connect(self.run_test_scan)
        self.figure, self.canvas, self.toolbar = setup_figure(self, self.layout_plot)
        self.figure.ax1 = self.figure.add_subplot(111)
        self.figure.ax2 = self.figure.ax1.twinx()
        self.figure.ax3 = self.figure.ax1.twinx()

    def run_scan(self):
        scan_idx = self.comboBox_scan_defs.currentIndex()
        name = self.lineEdit_exp_name.text()
        comment = self.lineEdit_exp_comment.text()
        repeat = self.spinBox_scan_repeat.value()
        delay = self.spinBox_scan_delay.value()
        if name:
            self.plans = self.scan_manager.generate_plan_list(scan_idx, name, comment, repeat, delay)
        else:
            message_box('Error', 'Please provide the name for the scan')

    def run_test_scan(self):
        name = self.lineEdit_exp_name.text()
        repeat = self.spinBox_scan_repeat.value()
        self.lineEdit_exp_name.setText(f'test {name}')
        self.spinBox_scan_repeat.setValue(1)
        self.run_scan()
        self.lineEdit_exp_name.setText(name)
        self.spinBox_scan_repeat.setValue(repeats)

    def update_scan_defs(self, scan_defs):
        self.comboBox_scan_defs.clear()
        self.comboBox_scan_defs.addItems(scan_defs)

    def draw_interpolated_data(self, df):
        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)
        if 'i0' in df and 'it' in df and 'energy' in df:
            transmission = np.array(np.log(df['i0'] / df['it']))
        if 'i0' in df and 'iff' in df and 'energy' in df:
            fluorescence = np.array(df['iff'] / df['i0'])
        if 'it' in df and 'ir' in df and 'energy' in df:
            reference = np.array(np.log(df['it'] / df['ir']))

        energy = np.array(df['energy'])
        edge = int(len(energy) * 0.02)
        #print(f'Before drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
        #print(f'After drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.legend(loc=2)
        self.figure.ax2.plot(energy[edge:-edge], fluorescence[edge:-edge], color='g', label='Total fluorescence')
        self.figure.ax2.legend(loc=1)
        self.figure.ax3.plot(energy[edge:-edge], reference[edge:-edge], color='b', label='Reference')
        self.figure.ax3.legend(loc=3)
        self.canvas.draw_idle()






