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
from PyQt5.QtWidgets import QMenu
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from sys import platform
from pathlib import Path
from .dialogs.BasicDialogs import message_box

from matplotlib.figure import Figure

from isstools.xasproject import xasproject
from xas.xray import k2e, e2k
from xas.file_io import load_binned_df_from_file

from isstools.widgets import widget_xview_data

if platform == 'darwin':
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview-mac.ui')
else:
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview.ui')


class XviewGui(*uic.loadUiType(ui_path)):


    def __init__(self, db=None,*args, **kwargs):

        self.db = db
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.widget_data = widget_xview_data.UIXviewData(db=db)
        self.layout_data.addWidget(self.widget_data)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())
