import pkg_resources
from PyQt5 import uic, QtCore
from matplotlib.widgets import RectangleSelector
from PyQt5.Qt import QSplashScreen, QObject
from PyQt5.QtGui import QPixmap
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
spectrometer_image1 = pkg_resources.resource_filename('isstools', 'Resources/spec_image1.png')
spectrometer_image2 = pkg_resources.resource_filename('isstools', 'Resources/spec_image2.png')

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
        self.parent = parent
        self.detector_dict = detector_dict
        self.plan_processor = plan_processor
        self.hhm = hhm
        self.cur_mouse_coords = None

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

        # self.toggle_selector.RS = RectangleSelector(self.figure_pilatus_image.ax,
        #                                             self.line_select_callback,
        #                                             drawtype='box',
        #                                             useblit=True,
        #                                             button=[1, 3],
        #                                             minspanx=5,
        #                                             minspany=5,
        #                                             spancoords='pixels',
        #                                             interactive=True)


        # self.pilatus100k_device.cam.trigger_mode.subscribe(self.update_pilatus_image)


        # self.pilatus100k_device.image.array_data.subscribe(self.update_pilatus_image)

        for i in range(1,5):
            self.add_roi_counts_total(i)

        for i in range(1, 5):
            self.add_roi_parameters(i)

        for _keys in self.subscription_dict.keys():
            self.add_pilatus_attribute(_keys)


        self.last_image_update_time = 0
        self.pilatus100k_device.cam.acquire.subscribe(self.update_image_widget)

    def add_roi_counts_total(self, ch):
        def update_roi_counts(value, **kwargs):
            getattr(self, 'label_counts_roi'+str(ch)).setText(f'{value} cts')

        getattr(self.pilatus100k_device, 'stats'+str(ch)).total.subscribe(update_roi_counts)

    def add_roi_parameters(self, ch):
        def update_roix_parameters(value, **kwargs):
            getattr(self, 'spinBox_roi' + str(ch) + '_min_x').setValue(value)

        def update_roiy_parameters(value, **kwargs):
            getattr(self, 'spinBox_roi' + str(ch) + '_min_y').setValue(value)

        def update_roix_size_parameters(value, **kwargs):
            getattr(self, 'spinBox_roi' + str(ch) + '_width').setValue(value)

        def update_roiy_size_parameters(value, **kwargs):
            getattr(self, 'spinBox_roi' + str(ch) + '_height').setValue(value)

        getattr(self.pilatus100k_device, 'roi' + str(ch)).min_xyz.min_x.subscribe(update_roix_parameters)
        getattr(self.pilatus100k_device, 'roi' + str(ch)).min_xyz.min_y.subscribe(update_roiy_parameters)

        getattr(self.pilatus100k_device, 'roi' + str(ch)).size.x.subscribe(update_roix_size_parameters)
        getattr(self.pilatus100k_device, 'roi' + str(ch)).size.y.subscribe(update_roiy_size_parameters)

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


    def line_select_callback(self, eclick, erelease):

        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        print(f'{x1 = :3.3f} {y1 = :3.3f} {x2 = :3.3f} {y2 = :3.3f}')

    def toggle_selector(self, event):
        print(f"key pressed")




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
        self.toolbar_pilatus_image = NavigationToolbar(self.canvas_pilatus_image, self, coordinates=True)
        self.verticalLayout_pilatus_image.addWidget(self.toolbar_pilatus_image)
        self.verticalLayout_pilatus_image.addWidget(self.canvas_pilatus_image, stretch=1)
        self.figure_pilatus_image.ax = self.figure_pilatus_image.add_subplot(111)
        self.canvas_pilatus_image.draw_idle()
        self.figure_pilatus_image.tight_layout()
        self.RS = RectangleSelector(self.figure_pilatus_image.ax,
                                                    self.line_select_callback,
                                                    drawtype='box',
                                                    useblit=True,
                                                    button=[1, 3],
                                                    minspanx=5,
                                                    minspany=5,
                                                    spancoords='pixels',
                                                    interactive=True)
        self.cid_box = self.canvas_pilatus_image.mpl_connect('key_press_event', self.toggle_selector)
        self.cid_start = self.canvas_pilatus_image.mpl_connect('button_press_event', self.roi_mouse_click_start)
        self.cid_move = self.canvas_pilatus_image.mpl_connect('motion_notify_event', self.roi_mouse_click_move)
        self.cid_finish = self.canvas_pilatus_image.mpl_connect('button_release_event', self.roi_mouse_click_finish)

    def update_pilatus_image(self):
        self.last_image_update_time = ttime.time()
        update_figure([self.figure_pilatus_image.ax],
                      self.toolbar_pilatus_image,
                      self.canvas_pilatus_image)

        _img = self.pilatus100k_device.image.array_data.value.reshape(195, 487)
        self.figure_pilatus_image.ax.imshow(_img.T, aspect='auto', vmin=0, vmax=5)

        for i in range(1,5):
            checkBox_widget = getattr(self, f'checkBox_roi{i}')
            if checkBox_widget.isChecked():
                pass



                # x, y, dx, dy = self.pilatus100k_device.get_roi_coords(i)
                # rect = patches.Rectangle((y, x), dy, dx, linewidth=1, edgecolor='r', facecolor='none')
                # self.figure_pilatus_image.ax.add_patch(rect)


        # Add the patch to the Axes


        # self.figure_pilatus_image.ax.autoscale(True)
        self.figure_pilatus_image.ax.set_xticks([])
        self.figure_pilatus_image.ax.set_yticks([])
        self.canvas_pilatus_image.draw_idle()

    def update_image_widget(self, value, old_value, **kwargs):
        if (value == 0) and (old_value == 1):
            if (ttime.time() - self.last_image_update_time) > 0.1:
                self.update_pilatus_image()

    def roi_mouse_click_start(self, event):
        # self.event = event
        if event.button == 3:
            self.cur_mouse_coords = (event.xdata, event.ydata)
            print('MOTION STARTED')

    def roi_mouse_click_move(self, event):
        if self.cur_mouse_coords is not None:
            self.cur_mouse_coords = (event.xdata, event.ydata)
            print(self.cur_mouse_coords)

    def roi_mouse_click_finish(self, event):
        if event.button == 3:
            if self.cur_mouse_coords is not None:
                self.cur_mouse_coords = None
                print('MOTION FINISHED')


    def stop_acquire_image(self):
        self.pilatus100k_device.cam.acquire.put(0)

    def acquire_image(self):
        self.plan_processor.add_plan_and_run_if_idle('take_pil100k_test_image_plan', {})
        # self.pilatus100k_device.cam.acquire.set(1).wait()
        # self.update_pilatus_image()

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
