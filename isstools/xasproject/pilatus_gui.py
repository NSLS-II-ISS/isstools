import pkg_resources
from PyQt5 import uic, QtCore
from matplotlib.widgets import RectangleSelector, Cursor
from PyQt5.Qt import QSplashScreen, QObject
from PyQt5.QtWidgets import QToolTip
from PyQt5.QtGui import QPixmap, QCursor
from isstools.dialogs.BasicDialogs import message_box
from isstools.elements.widget_motors import UIWidgetMotors
from functools import partial
from time import sleep
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib.patches as patches
import time as ttime

from isstools.elements.figure_update import update_figure

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_pilatus.ui')

class UIPilatusMonitor(*uic.loadUiType(ui_path)):
    def __init__(self,
                detector_dict=None,
                plan_processor=None,
                hhm=None,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)