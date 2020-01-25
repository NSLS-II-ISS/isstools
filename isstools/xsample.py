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


from matplotlib.figure import Figure
from isstools.elements.figure_update import update_figure


ui_path = pkg_resources.resource_filename('isstools', 'ui/xsample.ui')



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


    def addCanvas(self):
        self.figure_data = Figure()
        self.figure_data.set_facecolor(color='#FcF9F6')
        self.figure_data.ax = self.figure_data.add_subplot(111)
        self.canvas = FigureCanvas(self.figure_data)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout_data.addWidget(self.canvas)
        self.layout_data.addWidget(self.toolbar)
        self.canvas.draw()


    def update_status(self):
        flow_CH4 = self.mfcs[0].flow.read()['mfc_cart_CH4_flow']['value']
        self.label_CH4.setText('{:.1f} sccm'.format(flow_CH4))
        flow_CO = self.mfcs[1].flow.read()['mfc_cart_CO_flow']['value']
        self.label_CO.setText('{:.1f} sccm'.format(flow_CO))
        flow_H2 = self.mfcs[2].flow.read()['mfc_cart_H2_flow']['value']
        self.label_H2.setText('{:.1f} sccm'.format(flow_H2))

        now = ttime.time()
        some_time_ago = now - 3600 / 2
        df = self.archiver.tables_given_times(some_time_ago, now)

        masses = []
        for rga_mass in self.rga_masses:
            masses.append(str(rga_mass.get()))


        update_figure([self.figure_data.ax], self.toolbar, self.canvas)
        for rga_ch, mass in zip(self.rga_channels, masses):
            dataset = df[rga_ch.name]
            self.figure_data.ax.plot(dataset['time'],dataset['data'], label = f'{mass} amu')
        self.figure_data.ax.grid(alpha=0.4)
        self.figure_data.ax.relim(visible_only=True)
        self.figure_data.ax.autoscale_view(tight=True)
        self.figure_data.ax.set_yscale('log')
        self.figure_data.tight_layout()
        self.figure_data.ax.legend(loc=6)

        self.canvas.draw_idle()


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



