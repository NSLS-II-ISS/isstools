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
from isstools.elements.figure_update import update_figure
from isstools.elements.parameter_handler import parse_plan_parameters, return_parameters_from_widget
from isstools.widgets import widget_energy_selector

from isstools.process_callbacks.callback import run_router


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_camera.ui')

class UICamera(*uic.loadUiType(ui_path)):
    def __init__(self,
                 camera_dict={},
                 parent_gui = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.push_show_image.clicked.connect(self.show_image)
        self.camera_dict = camera_dict





    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax = self.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        #self.figure.ax3.grid(alpha = 0.4)
        self.canvas.draw_idle()

    def show_image(self):
        camera = self.camera_dict['camera_sample3']
        print(camera)
        image=camera.image.image
        print(image)
        a=self.figure.ax.imshow(image, cmap='gray')
        print(a)
        self.canvas.draw_idle()





