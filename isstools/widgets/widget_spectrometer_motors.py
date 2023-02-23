import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from PyQt5.Qt import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np

from isstools.dialogs import MoveMotorDialog
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
from isstools.elements.transformations import  range_step_2_start_stop_nsteps
from isstools.widgets import widget_johann_tools
from xas.spectrometer import analyze_elastic_scan
from ..elements.liveplots import XASPlot, NormPlot#, XASPlotX
from ..elements.elements import get_spectrometer_line_dict
# from isstools.elements.liveplots import NormPlot
from isstools.widgets import widget_emission_energy_selector
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_motors_tab.ui')

class UISpectrometerMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 # plan_processor,
                 # hhm,
                 db,
                 # johann_emission,
                 # detector_dictionary,
                 motor_dictionary,
                 # shutter_dictionary,
                 # aux_plan_funcs,
                 # ic_amplifiers,
                 # service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.RE = RE
        self.db = db
        self.parent = parent
        self.motor_dictonary = motor_dictionary
