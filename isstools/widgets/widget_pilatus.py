import pkg_resources
from PyQt5 import uic, QtCore
from PyQt5.QtGui import QPixmap
from isstools.elements.widget_motors import UIWidgetMotors
from functools import partial
from time import sleep
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_pilatus.ui')
spectrometer_image1 = pkg_resources.resource_filename('isstools', 'Resources/spec_image1.png')
spectrometer_image2 = pkg_resources.resource_filename('isstools', 'Resources/spec_image2.png')

class UIPilatusMonitor(*uic.loadUiType(ui_path)):
    def __init__(self,
                detector_dict = None,
                hhm = None,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.detector_dict = detector_dict
        self.hhm = hhm


        self.pilatus100k_dict = self.detector_dict['Pilatus 100k']
        self.pilatus100k_device = self.detector_dict['Pilatus 100k']['device']
        self.addCanvas()

        self.subscription_dict = {'exposure': self.pilatus100k_device.cam.acquire_time,
                                  'num_of_images': self.pilatus100k_device.cam.num_images,
                                  'set_energy' : self.pilatus100k_device.cam.set_energy,
                                  'cutoff_energy': self.pilatus100k_device.cam.threshold_energy}

        self.gain_menu = {0: "7-30keV/Fast/LowG",
                          1: "5-18keV/Med/MedG",
                          2: "3-6keV/Slow/HighG",
                          3: "2-5keV/Slow/UltraG"}
        for i in range(4):
            self.comboBox_shapetime.addItem(self.gain_menu[i])

        self.comboBox_shapetime.currentIndexChanged.connect(self.change_pilatus_gain)
        self.pilatus100k_device.cam.gain_menu.subscribe(self.update_gain_combobox)

        self.radioButton_single_exposure.toggled.connect(self.update_acquisition_mode)
        self.radioButton_continuous_exposure.toggled.connect(self.update_acquisition_mode)

        self.pushButton_start.clicked.connect(self.acquire_image)
        self.pushButton_stop.clicked.connect(self.stop_acquire_image)

        self.checkBox_detector_settings.clicked.connect(self.open_detector_setting)

        self.checkBox_enable_energy_change.clicked.connect(self.open_energy_change)
        self.hhm.energy.user_readback.subscribe(self.read_mono_energy)
        self.pushButton_move_energy.clicked.connect(self.set_mono_energy)

        self.pilatus100k_device.image.array_data.subscribe(self.update_pilatus_image)

        for i in range(1,5):
            def update_roi_counts(value, **kwargs):
                getattr(self, 'label_counts_roi'+str(i)).setText(f'{value} cts')
            getattr(self.pilatus100k_device, 'stats'+str(i)).total.subscribe(update_roi_counts)

        for i in range(1,5):
            def update_roix_parameters(value, **kwargs):
                getattr(self, 'spinBox_roi' + str(i) + '_min_x').setValue(value)

            def update_roiy_parameters(value, **kwargs):
                getattr(self, 'spinBox_roi' + str(i) + '_min_y').setValue(value)

            def update_roix_size_parameters(value, **kwargs):
                getattr(self, 'spinBox_roi' + str(i) + '_width').setValue(value)

            def update_roiy_size_parameters(value, **kwargs):
                getattr(self, 'spinBox_roi' + str(i) + '_height').setValue(value)


            getattr(self.pilatus100k_device, 'roi'+  str(i)).min_xyz.min_x.subscribe(update_roix_parameters)
            getattr(self.pilatus100k_device, 'roi' + str(i)).min_xyz.min_y.subscribe(update_roiy_parameters)

            getattr(self.pilatus100k_device, 'roi' + str(i)).size.x.subscribe(update_roix_size_parameters)
            getattr(self.pilatus100k_device, 'roi' + str(i)).size.y.subscribe(update_roiy_size_parameters)


        for _keys in self.subscription_dict.keys():
            self.add_pilatus_attribute(_keys)

    def set_mono_energy(self):
        if self.checkBox_enable_energy_change.isChecked():
            _energy = self.spinBox_mono_energy.value()
            self.hhm.energy.user_setpoint.set(_energy).wait()

    def read_mono_energy(self, value, **kwargs):
        self.label_current_energy.setText(f'{value:4.1f} eV')

    def open_energy_change(self):
        if self.checkBox_enable_energy_change.isChecked():
            self.spinBox_mono_energy.setEnabled(True)
        else:
            self.spinBox_mono_energy.setEnabled(False)



    def open_detector_setting(self):

        if self.checkBox_detector_settings.isChecked():
            self.doubleSpinBox_set_energy.setEnabled(True)
            self.doubleSpinBox_cutoff_energy.setEnabled(True)
        else:
            self.doubleSpinBox_set_energy.setEnabled(False)
            self.doubleSpinBox_cutoff_energy.setEnabled(False)



    def addCanvas(self):
        self.figure_pilatus_image = Figure()
        self.figure_pilatus_image.set_facecolor(color='#FcF9F6')
        self.canvas_pilatus_image = FigureCanvas(self.figure_pilatus_image)
        self.figure_pilatus_image.ax = self.figure_pilatus_image.add_subplot(111)
        _img = self.pilatus100k_device.image.array_data.value.reshape(195, 487)
        self.figure_pilatus_image.ax.imshow(_img.T, aspect='auto')
        self.figure_pilatus_image.ax.set_xticks([])
        self.figure_pilatus_image.ax.set_yticks([])
        self.toolbar_pilatus_image = NavigationToolbar(self.canvas_pilatus_image, self, coordinates=True)
        self.verticalLayout_pilatus_image.addWidget(self.toolbar_pilatus_image)
        self.verticalLayout_pilatus_image.addWidget(self.canvas_pilatus_image, stretch=1)
        self.canvas_pilatus_image.draw_idle()
        self.figure_pilatus_image.tight_layout()
        # self.figure_pilatus_image.ax.grid(alpha=0.4)
        # self.figure_binned_scans = Figure()
        # self.figure_binned_scans.set_facecolor(color='#FcF9F6')
        # self.canvas_binned_scans = FigureCanvas(self.figure_binned_scans)
        # self.figure_binned_scans.ax = self.figure_binned_scans.add_subplot(111)
        # self.toolbar_binned_scans = NavigationToolbar(self.canvas_binned_scans, self, coordinates=True)
        # self.plot_binned_scans.addWidget(self.toolbar_binned_scans)
        # self.plot_binned_scans.addWidget(self.canvas_binned_scans)
        # self.canvas_binned_scans.draw_idle()
        # self.figure_binned_scans.ax.grid(alpha=0.4)

    def update_pilatus_image(self, value, **kwargs):
        pass


    def stop_acquire_image(self):
        self.pilatus100k_device.cam.acquire.put(0)

    def acquire_image(self):
        self.pilatus100k_device.cam.acquire.set(1).wait()

    def update_acquisition_mode(self):
        if self.radioButton_single_exposure.isChecked():

            self.pilatus100k_device.cam.image_mode.set(0).wait()
            self.pilatus100k_device.cam.trigger_mode.set(0).wait()
        else:
            self.pilatus100k_device.cam.image_mode.set(2).wait()
            self.pilatus100k_device.cam.trigger_mode.set(4).wait()

    def add_pilatus_attribute(self, attribute_key):

        def update_item(_attr_key, _attr_signal):
            _current_value = getattr(self, "doubleSpinBox_"+_attr_key).value()
            _attr_signal.set(_current_value).wait()

        def update_item_value(value ,**kwargs):
            if attribute_key == "exposure":
                unit = 's'
            elif attribute_key == 'num_of_images':
                unit = " "
            else:
                unit = "keV"
            getattr(self, "label_"+attribute_key).setText(f"{value:2.3f} {unit}")
            getattr(self, "doubleSpinBox_"+attribute_key).setValue(value)

        getattr(self, "doubleSpinBox_"+attribute_key).valueChanged.connect(partial(update_item, attribute_key, self.subscription_dict[attribute_key]))
        self.subscription_dict[attribute_key].subscribe(update_item_value)

    def change_pilatus_gain(self):
        _current_indx = self.comboBox_shapetime.currentIndex()
        self.pilatus100k_device.cam.gain_menu.set(_current_indx).wait()

    def update_gain_combobox(self, value, **kwargs):
        self.comboBox_shapetime.setCurrentIndex(value)
