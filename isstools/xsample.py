import os
import re
import sys
import time as ttime
import matplotlib
matplotlib.use('WXAgg')
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import pkg_resources
from PyQt5 import QtGui, QtWidgets, QtCore, uic
from PyQt5.Qt import QSplashScreen, QObject
from PyQt5.QtCore import QSettings, QThread, pyqtSignal, QTimer, QDateTime
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
import bluesky.plan_stubs as bps

from matplotlib.figure import Figure
from isstools.elements.figure_update import update_figure


ui_path = pkg_resources.resource_filename('isstools', 'ui/xsample.ui')

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()


# gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class XsampleGui(*uic.loadUiType(ui_path)):

    # class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self,
                 mfcs = [],
                 rga_channels = [],
                 rga_masses = [],
                 RE = [],
                 archiver = [],
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.mfcs = mfcs
        self.rga_channels = rga_channels
        self.rga_masses = rga_masses
        self.RE = RE
        self.archiver = archiver
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(2000)
        self.timer_update_time.timeout.connect(self.update_status)
        self.timer_update_time.start()

        self.spinBox_CH4.valueChanged.connect(self.set_mfc_cart_flow)
        self.spinBox_CO.valueChanged.connect(self.set_mfc_cart_flow)
        self.spinBox_H2.valueChanged.connect(self.set_mfc_cart_flow)

        self.spinBox_CH4.setValue(mfcs[0].flow.get_setpoint())
        self.spinBox_CO.setValue(mfcs[1].flow.get_setpoint())
        self.spinBox_H2.setValue(mfcs[2].flow.get_setpoint())

        for indx in range(8):
            getattr(self, f'checkBox_rga{indx+1}').toggled.connect(self.update_status)


        for indx, rga_mass in enumerate(self.rga_masses):
            getattr(self, f'spinBox_rga_mass{indx + 1}').setValue(rga_mass.get())
            getattr(self, f'spinBox_rga_mass{indx + 1}').valueChanged.connect(self.change_rga_mass)




    def addCanvas(self):
        self.figure_rga = Figure()
        self.figure_rga.set_facecolor(color='#FcF9F6')
        self.figure_rga.ax = self.figure_rga.add_subplot(111)
        self.canvas_rga = FigureCanvas(self.figure_rga)
        self.toolbar_rga = NavigationToolbar(self.canvas_rga, self)
        self.layout_rga.addWidget(self.canvas_rga)
        self.layout_rga.addWidget(self.toolbar_rga)
        self.canvas_rga.draw()

        self.figure_mfc = Figure()
        self.figure_mfc.set_facecolor(color='#FcF9F6')
        self.figure_mfc.ax = self.figure_mfc.add_subplot(111)
        self.canvas_mfc = FigureCanvas(self.figure_mfc)
        self.toolbar_mfc = NavigationToolbar(self.canvas_mfc, self)
        self.layout_mfc.addWidget(self.canvas_mfc)
        self.layout_mfc.addWidget(self.toolbar_mfc)
        self.canvas_mfc.draw()

    def change_rga_mass(self):
        sender_object = QObject().sender()
        print(sender_object.objectName())
        indx=sender_object.objectName()[-1]
        self.RE(bps.mv(self.rga_masses[int(indx)-1],sender_object.value()))


    def update_status(self):
        flow_CH4 = self.mfcs[0].flow.read()['mfc_cart_CH4_flow']['value']
        self.label_CH4.setText('{:.1f} sccm'.format(flow_CH4))
        flow_CO = self.mfcs[1].flow.read()['mfc_cart_CO_flow']['value']
        self.label_CO.setText('{:.1f} sccm'.format(flow_CO))
        flow_H2 = self.mfcs[2].flow.read()['mfc_cart_H2_flow']['value']
        self.label_H2.setText('{:.1f} sccm'.format(flow_H2))

        now = ttime.time()

        timewindow = self.doubleSpinBox_timewindow.value()

        some_time_ago = now - 3600 * timewindow
        df = self.archiver.tables_given_times(some_time_ago, now)

        masses = []
        for rga_mass in self.rga_masses:
            masses.append(str(rga_mass.get()))


        update_figure([self.figure_rga.ax], self.toolbar_rga, self.canvas_rga)
        for rga_ch, mass in zip(self.rga_channels, masses):
            dataset = df[rga_ch.name]
            indx = rga_ch.name[-1]
            if getattr(self, f'checkBox_rga{indx}').isChecked():
                self.figure_rga.ax.plot(dataset['time'],dataset['data'], label = f'{mass} amu')
        self.figure_rga.ax.grid(alpha=0.4)
        self.figure_rga.ax.relim(visible_only=True)
        self.figure_rga.ax.autoscale_view(tight=True)
        self.figure_rga.ax.set_yscale('log')
        self.figure_rga.tight_layout()
        self.figure_rga.ax.legend(loc=6)
        self.canvas_rga.draw_idle()


    def set_mfc_cart_flow(self):
        sender = QObject()
        sender_object = sender.sender()
        sender_name = sender_object.objectName()
        value = sender_object.value()
        mfc_dict = {'spinBox_CH4': self.mfcs[0],
                    'spinBox_CO': self.mfcs[1],
                    'spinBox_H2': self.mfcs[2],
                    }

        mfc_dict[sender_name].flow.put(value)




if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())



