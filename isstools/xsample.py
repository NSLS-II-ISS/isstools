import os
import re
import sys
import time
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

from matplotlib.figure import Figure

from isstools.xasproject import xasproject
from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file


ui_path = pkg_resources.resource_filename('isstools', 'ui/xsample'
                                                      '.ui')

#gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class XsampleGui(*uic.loadUiType(ui_path)):

#class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()


    def addCanvas(self):
        self.figure_data = Figure()
        self.figure_data.set_facecolor(color='#FcF9F6')
        self.figure_data.ax = self.figureBinned.add_subplot(111)
        self.canvas = FigureCanvas(self.figure_data)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout_data.addWidget(self.canvas)
        self.layout_data.addWidget(self.toolbar)
        self.canvas.draw()



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())


