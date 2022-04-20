import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore, QtWidgets

from PyQt5.QtCore import QThread, QSettings
from isstools.elements.qmicroscope import Microscope




ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_view.ui')


class UISampleView(*uic.loadUiType(ui_path)):


    def __init__(self,
                camera_dict={},
                 cam1_url='http://10.66.59.30:8083/FfmStream1.jpg',
                 cam2_url='http://10.66.59.30:8082/FfmStream1.jpg',

                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.camera_dict = camera_dict

        self.camera1 = self.camera_dict['camera_sample1']
        self.camera2 = self.camera_dict['camera_sample2']

        self.interaction_mode = 'default'

        self.pushButton_visualize_sample.clicked.connect(self.visualize_sample)
        self.pushButton_visualize_beam.clicked.connect(self.visualize_beam)

        self.spinBox_image_min.valueChanged.connect(self.update_image_limits)
        self.spinBox_image_max.valueChanged.connect(self.update_image_limits)

        self.pushButton_calibration_mode.clicked.connect(self.set_to_calibration_mode)

        self.cam1_url = cam1_url
        self.sample_cam1 = Microscope(parent = self, mark_direction=1,)
        self.sample_cam1.url = self.cam1_url
        self.sample_cam1.fps = 10

        self.layout_sample_cam1.addWidget(self.sample_cam1)
        self.sample_cam1.acquire(True)

        self.cam2_url = cam2_url
        self.sample_cam2 = Microscope(parent=self, mark_direction=0, )
        self.sample_cam2.url = self.cam2_url
        self.sample_cam2.fps = 10

        self.layout_sample_cam2.addWidget(self.sample_cam2)
        self.sample_cam2.acquire(True)


    def visualize_beam(self):
        exposure = self.doubleSpinBox_exposure_beam.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)

    def visualize_sample(self):
        exposure = self.doubleSpinBox_exposure_sample.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)


    def update_image_limits(self):
        vmin = self.spinBox_image_min.value()
        vmax = self.spinBox_image_max.value()
        print(vmin, vmax)


    def set_to_calibration_mode(self, state):
        if state:
            self.interaction_mode = 'calibration'
        else:
            self.interaction_mode = 'default'



