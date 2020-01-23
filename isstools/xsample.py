import os
import re
import sys
import time
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
from sys import platform
from pathlib import Path
import pandas as pd

import bluesky.plan_stubs as bps

from matplotlib.figure import Figure

from isstools.xasproject import xasproject
from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file

ui_path = pkg_resources.resource_filename('isstools', 'ui/xsample.ui')



# gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class XsampleGui(*uic.loadUiType(ui_path)):

    # class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self, mfcs = [], RE = [], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.mfcs = mfcs
        self.RE = RE


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



