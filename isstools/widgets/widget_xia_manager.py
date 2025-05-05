import re
import time as ttime
import bluesky.plan_stubs as bps

import numpy as np
import pkg_resources

from PyQt5 import uic,  QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from PyQt5.Qt import QSplashScreen, QObject
import numpy
from PyQt5 import  QtWidgets
from scipy.optimize import curve_fit


from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure
from isstools.elements.roi_widget import ROIWidget

from isstools.widgets import widget_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xia_manager.ui')


class UIXIAManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 service_plan_funcs=None,
                 ge_detector = None,
                 RE=None,

                 *args,
                 **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.figure_mca, self.canvas_mca,self.toolbar_mca = setup_figure(self, self.layout_plot_mca)
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.ge_detector = ge_detector
        self.populate_layouts()

        self.change_collection_modes = {
            "MCA spectra": 0,
            "MCA mapping": 1,
            "SCA mapping": 2
        }

        self.comboBox_collection_mode.addItems(list(self.change_collection_modes.keys()))
        self.comboBox_collection_mode.currentTextChanged.connect(self.change_collection_mode)
        self.push_acquire.clicked.connect(self.acquire)
        self.push_reorder_rois.clicked.connect(self.reorder_rois_by_lo)
        self.push_ch1_to_all.clicked.connect(self.copy_ch1_to_all)
        self.push_calibrate.clicked.connect(self.calibrate)


        self.spinBox_acq_time.valueChanged.connect(self.set_acquition_time)
        self.ge_detector.settings.acquiring.subscribe(self.on_change_acquisition_status)
        self.label_acquiring.setStyleSheet("")

        self.canvas_mca.mpl_connect("button_press_event", self.on_canvas_click)

    def on_canvas_click(self, event):
        if event.button == 3:  # Right-click (1=left, 2=middle, 3=right)
            if event.xdata is not None:
                self.measured_energy = event.xdata
                self.spinBox_measured_energy.setValue(int(self.measured_energy))

    def on_change_acquisition_status(self, value=None, *args, **kwargs):
        if value == 1:
            self.label_acquiring.setStyleSheet("background-color: red; color: black;")
            self.label_acquiring.setText("Acquiring...")
        else:
            self.label_acquiring.setText("Idle")
            self.label_acquiring.setStyleSheet("")

    def populate_layouts(self):
        self.spinBox_acq_time.setValue(self.ge_detector.settings.real_time.get())
        for ch in range(1, 33):
            checkbox = QtWidgets.QCheckBox(f'Channel {ch}')
            checkbox.setCheckState(True)
            checkbox.setTristate(False)
            self.verticalLayout_channels.addWidget(checkbox)
            setattr(self, f'checkbox_ch{ch}', checkbox)

        self.roi_widgets = []
        for roi in range(1,5):
            layout = getattr(self, f'gridLayout_roi{roi}')
            _roi = []
            for ch in range(1, 33):
                roi_widget=ROIWidget(ge_detector=self.ge_detector, roi = roi, channel = ch)
                _roi.append(roi_widget)
                layout.addWidget(roi_widget, ch, 0)
            self.roi_widgets.append(_roi)

        # ✅ Add mode-switching ComboBox logic here


        # Optional: Initialize current mode from detector
        try:
            current_mode = self.ge_detector.mode.get()
            index = self.comboBox_collection_mode.findText(current_mode)
            if index != -1:
                self.comboBox_collection_mode.setCurrentIndex(index)
        except Exception as e:
            print(f"Could not get initial mode: {e}")

    def set_acquition_time(self):
        self.ge_detector.settings.real_time.set(self.spinBox_acq_time.value())
        self.ge_detector.settings.live_time.set(self.spinBox_acq_time.value())

    def copy_ch1_to_all(self):
        self.ge_detector.settings.copy_ch1_to_all.put(1)
        self.ge_detector.settings.copy_roi_to_sca.put(1)

    def reorder_rois_by_lo(self):
        for ch in range(1, 33):
            widgets = [self.roi_widgets[roi_idx][ch - 1] for roi_idx in range(4)]

            # Collect current ROI bounds and widget
            roi_data = []
            for w in widgets:
                lo = w.roi_lo.get()
                hi = w.roi_hi.get()
                roi_data.append({'widget': w, 'lo': lo, 'hi': hi})

            # Sort by lo value
            roi_data_sorted = sorted(roi_data, key=lambda x: x['lo'])

            #Reassign R0–R3 based on sorted order
            for unsorted_item, sorted_item in zip(roi_data, roi_data_sorted):
                lo = sorted_item['lo']
                hi = sorted_item['hi']
                widget = unsorted_item['widget']

                # Block signals to prevent triggering update_detector multiple times
                widget.spin_roi_lo.blockSignals(True)
                widget.spin_roi_hi.blockSignals(True)
                widget.spin_roi_lo.setValue(widget.pixel_to_energy(lo))
                widget.spin_roi_hi.setValue(widget.pixel_to_energy(hi))
                widget.spin_roi_lo.blockSignals(False)
                widget.spin_roi_hi.blockSignals(False)

                # update the detector
                widget.update_detector()

    def change_collection_mode(self):
        mode = self.comboBox_collection_mode.currentText()
        self.ge_detector.settings.collection_mode.put(self.change_collection_modes[mode])

    def acquire(self):
        #TODO open shutter self.shutter_dict
        print('XIA acquisition starting...')
        acq_time = self.spinBox_acq_time.value()

        self.ge_detector.settings.start.put(1)
        start_time = ttime.time()
        timeout = 0.5  # seconds
        while self.ge_detector.settings.acquiring.get() == 0:
            if ttime.time() - start_time > timeout:
                pass
            ttime.sleep(0.1)
        while self.ge_detector.settings.acquiring.get() == 1:
            ttime.sleep(0.1)
        self.acquired = True
        self.plot_traces()
        self.canvas_mca.draw_idle()
        print('XIA acquisition complete')

    def plot_traces(self):
        update_figure([self.figure_mca.ax], self.toolbar_mca, self.canvas_mca)
        for jj in range(1,20):
            _mca = getattr(self.ge_detector._channels, f'mca{jj}').get()
            mca = np.array(_mca[0])
            energy = (np.array(range(len(mca)))*self.ge_detector.settings.max_energy/
                      self.ge_detector.settings.mca_len)
            self.figure_mca.ax.plot(energy[200:],  mca[200:], label=f'Channel {jj}')


    def calibrate(self):
        def gaussian(x, a, x0, sigma, offset):
            return a * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2)) + offset

        update_figure([self.figure_mca.ax], self.toolbar_mca, self.canvas_mca)
        for jj in range(1,20):
            _mca = getattr(self.ge_detector._channels, f'mca{jj}').get()
            mca = np.array(_mca[0])
            energy = (np.array(range(len(mca)))*self.ge_detector.settings.max_energy/
                      self.ge_detector.settings.mca_len)

            center = self.spinBox_measured_energy.value()
            width = 500
            lower_bound = center - width
            upper_bound = center + width
            mask = (energy >= lower_bound) & (energy <= upper_bound)

            energy_filtered = energy[mask]
            mca_filtered = mca[mask]
            a_guess = mca_filtered.max()
            x0_guess = center
            sigma_guess = 10
            offset_guess = np.median(mca_filtered)
            p0 = [a_guess, x0_guess, sigma_guess, offset_guess]
            popt, pcov = curve_fit(gaussian, energy_filtered, mca_filtered, p0=p0)

            # Extract fit parameters
            a_fit, x0_fit, sigma_fit, offset_fit = popt
            self.figure_mca.ax.plot(energy[200:],  mca[200:], label=f'Channel {jj}')
            self.figure_mca.ax.plot(energy_filtered, gaussian(energy_filtered, *popt),
                                    linestyle="--")
            print(f'x0 fit: {x0_fit}')



