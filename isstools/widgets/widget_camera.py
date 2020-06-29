import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from PyQt5 import uic, QtCore
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import time
from pyzbar.pyzbar import decode as pzDecode
import bluesky.plan_stubs as bps
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
                 sample_stage = {},
                 RE = None,
                 parent_gui = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.sample_stage = sample_stage
        self.RE = RE
        self.addCanvas()
        self.cid = self.canvas_c1.mpl_connect('button_press_event', self.set_hcursor)
        self.cid = self.canvas_c2.mpl_connect('button_press_event', self.set_vcursor)
        self.h_vc = None
        self.h_hc = None

        self.push_show_image.clicked.connect(self.show_image)
        self.push_zero_stage.clicked.connect(self.zero_stage)
        self.camera_dict = camera_dict

        self.parent_gui = parent_gui
        self.settings = QSettings(self.parent_gui.window_title, 'XLive')
        # self.spinBox_zero_x.setValue(self.settings.value('sample_stage_zero_x', defaultValue=250, type=int))
        # self.spinBox_zero_y.setValue(self.settings.value('sample_stage_zero_y', defaultValue=250, type=int))

        self.timer_track_camera = QtCore.QTimer(self)
        self.timer_track_camera.setInterval(1000)
        self.timer_track_camera.timeout.connect(self.track_camera)
        #self.timer_track_camera.start()


    def addCanvas(self):
        self.figure_c1 = Figure()
        self.figure_c1.set_facecolor(color='#FcF9F6')
        self.canvas_c1 = FigureCanvas(self.figure_c1)
        self.figure_c1.ax = self.figure_c1.add_subplot(111)

        self.figure_c1.tight_layout()
        self.toolbar_c1 = NavigationToolbar(self.canvas_c1, self, coordinates=True)
        self.plot_camera1.addWidget(self.toolbar_c1)
        self.plot_camera1.addWidget(self.canvas_c1)
        self.canvas_c1.draw_idle()

        self.figure_c2 = Figure()
        self.figure_c2.set_facecolor(color='#FcF9F6')
        self.canvas_c2 = FigureCanvas(self.figure_c2)
        self.figure_c2.ax = self.figure_c2.add_subplot(111)

        self.figure_c2.tight_layout()
        self.toolbar_c2 = NavigationToolbar(self.canvas_c2, self, coordinates=True)
        self.plot_camera2.addWidget(self.toolbar_c2)
        self.plot_camera2.addWidget(self.canvas_c2)
        self.canvas_c2.draw_idle()

        self.figure_qr = Figure()
        self.figure_qr.set_facecolor(color='#FcF9F6')
        self.canvas_qr = FigureCanvas(self.figure_qr)
        self.figure_qr.ax = self.figure_qr.add_subplot(111)

        self.figure_qr.tight_layout()
        self.toolbar_qr = NavigationToolbar(self.canvas_qr, self, coordinates=True)
        self.plot_camera_qr.addWidget(self.toolbar_qr)
        self.plot_camera_qr.addWidget(self.canvas_qr)
        self.canvas_qr.draw_idle()


    # def show_image(self, camera_):


    def show_image(self):
        if self.push_track.isChecked():
            self.timer_track_camera.start()
        else:
            self.timer_track_camera.singleShot(0, self.track_camera)

    def track_camera(self):
        camera1 = self.camera_dict['camera_sample1']
        camera2 = self.camera_dict['camera_sample2']
        camera_qr = self.camera_dict['camera_sample4']
        image1 = camera1.image.image
        image2 = camera2.image.image
        image_qr = camera_qr.image.image
        self.figure_c1.ax.imshow(image1, cmap='gray')
        self.figure_c2.ax.imshow(image2, cmap='gray')
        self.figure_qr.ax.imshow(image_qr, cmap='gray')
        self.canvas_c1.draw_idle()
        self.canvas_c2.draw_idle()
        self.canvas_qr.draw_idle()

    def zero_stage(self):
        self.settings.setValue('sample_stage_zero_x', self.spinBox_zero_x)
        self.settings.setValue('sample_stage_zero_y', self.spinBox_zero_y)
        calib = 10.957
        camera_qr = self.camera_dict['camera_sample4']
        image_qr = camera_qr.image.image
        qr_codes = pzDecode(image_qr)
        if qr_codes:
            for qr_code in qr_codes:
                qr_text = qr_code.data.decode('utf8')
                if qr_text == '0 position':
                    self.label_qrcode.setText(qr_text)
                    self.qrcode_zero_y = qr_code.rect.top
                    self.qrcode_zero_x = qr_code.rect.left
                    delta_x = (self.spinBox_zero_x.value() - self.qrcode_zero_x)/calib
                    delta_y = (self.spinBox_zero_y.value() - self.qrcode_zero_y)/calib
                    print(delta_x, delta_y)
                    self.RE(bps.mvr(self.sample_stage.x, -delta_x))
                    self.RE(bps.mvr(self.sample_stage.y, delta_y))
                    self.show_image()




    def set_vcursor(self, event):
        if self.h_vc:
            self.h_vc.remove()
        if event.button == 3:
            y1, y2 = self.figure_c2.ax.get_ylim()
            self.h_vc = self.figure_c2.ax.vlines(event.xdata, y1,y2, color = 'green' )
            self.canvas_c2.draw_idle()

    def set_hcursor(self, event):

        if event.button == 3:
            if self.h_hc:
                self.h_hc.remove()
            x1, x2 = self.figure_c1.ax.get_xlim()
            self.h_hc = self.figure_c1.ax.hlines(event.ydata, x1, x2, color = 'green' )
            self.canvas_c1.draw_idle()










