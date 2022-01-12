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


from isstools.elements.figure_update import update_figure, setup_figure

from isstools.widgets import widget_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sdd_manager.ui')


class UISDDManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 service_plan_funcs,
                 xs,
                 RE,
                 *args,
                 **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.figure_mca, self.canvas_mca,self.toolbar_mca = setup_figure(self, self.layout_plot_mca)
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.xs = xs
        self.roi_plots = []

        self.widget_energy_selector = widget_energy_selector.UIEnergySelector(emission=True)
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_roi_labels)
        self.timer_update_time.start()

        self.push_xs3_acquire.clicked.connect(self.xs3_acquire)

        self.colors = ['r', 'b', 'g', 'm']
        self.num_channels = 4
        self.num_rois = 4
        self.roi_values = numpy.zeros((4, 4, 2))
        self.roi_plots = []
        self.acquired = 0


        self.checkbox_ch = 'checkBox_ch{}_show'

        for indx in range(self.num_channels):
             getattr(self, self.checkbox_ch.format(indx + 1)).stateChanged.connect(self.plot_traces)

        self.checkbox_roi = 'checkBox_roi{}_show'
        for indx in range(self.num_rois):
             getattr(self, self.checkbox_roi.format(indx + 1)).stateChanged.connect(self.update_roi_plot)

        self.lo_hi = ['lo','hi']
        self.lo_hi_def = {'lo':'low', 'hi':'high'}
        self.spinbox_roi = 'spinBox_ch{}_roi{}_{}'
        self.label_roi_rbk = 'label_ch{}_roi{}_{}_rbk'


        self.checkbox_fix_rois = 'checkBox_ch{}_fix_roi'
        for indx in range(1,self.num_channels):
            checkbox_name = self.checkbox_fix_rois.format(indx+1)
            checkbox_object = getattr(self, checkbox_name)
            checkbox_object.stateChanged.connect(self.fix_rois)


        self.update_spinboxes()

        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch + 1, indx_roi + 1, self.lo_hi[indx_lo_hi])
                    spinbox_object = getattr(self, spinbox_name)
                    spinbox_object.editingFinished.connect(self.set_roi_value)



    def fix_rois(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        indx_ch = sender_object[11]

        if sender.sender().isChecked():
            for jj in range(2):
                # repeat to make sure no values are forced
                for indx_roi in range(self.num_rois):
                    for indx_lo_hi in range(2):
                        spinbox_name_ch1 = self.spinbox_roi.format(1, indx_roi + 1, self.lo_hi[indx_lo_hi])
                        spinbox_object_ch1 = getattr(self, spinbox_name_ch1)
                        value = spinbox_object_ch1.value()

                        spinbox_name = self.spinbox_roi.format(indx_ch, indx_roi + 1, self.lo_hi[indx_lo_hi])
                        spinbox_object = getattr(self, spinbox_name)
                        spinbox_object.setValue(value)
                        spinbox_object.setEnabled(False)
        else:
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch, indx_roi + 1, self.lo_hi[indx_lo_hi])
                    spinbox_object = getattr(self, spinbox_name)
                    spinbox_object.setEnabled(True)

    def set_roi_value(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        indx_ch = sender_object[10]
        indx_roi = sender_object[15]
        lo_hi = sender_object[17:]
        signal = self.get_roi_signal(indx_ch, indx_roi, self.lo_hi.index(lo_hi))
        value = sender.sender().value()
        signal.put(int(value/10))
        print(f' Value {value}')
        self.roi_values[int(indx_ch)-1, int(indx_roi)-1, self.lo_hi.index(lo_hi)]= value
        self.update_roi_plot()

    def get_roi_signal(self, indx_ch,indx_roi,indx_lo_hi):
        signal_ch = getattr(self.xs, 'channel{}'.format(indx_ch))
        signal_roi = getattr(signal_ch.rois, 'roi0{}'.format(indx_roi))
        signal = getattr(signal_roi, 'bin_{}'.format(self.lo_hi_def[self.lo_hi[indx_lo_hi]]))
        return signal


    def update_roi_labels(self):
        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    label_name =self.label_roi_rbk.format(indx_ch+1, indx_roi+1, self.lo_hi[indx_lo_hi])
                    label_object = getattr(self,label_name)
                    value = self.get_roi_signal( indx_ch+1, indx_roi+1, indx_lo_hi).get()
                    label_object.setText(str(value*10))


    def update_spinboxes(self):
       # print('Updating spinboxes')
        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch+1,indx_roi+1,self.lo_hi[indx_lo_hi])
                    spinbox_object = getattr(self,spinbox_name)
                    value = self.get_roi_signal(indx_ch+1, indx_roi+1, indx_lo_hi).get() * 10
                    spinbox_object.setValue(value)
                    self.roi_values[indx_ch,indx_roi,indx_lo_hi] = value
        self.update_roi_plot()

    def update_roi_plot(self):
        for roi_plot in self.roi_plots:
            self.figure_mca.ax.lines.remove(roi_plot[0])
        self.roi_plots = []
        ylims=self.figure_mca.ax.get_ylim()
        for indx_ch in range(self.num_channels):
            show_ch = getattr(self, 'checkBox_ch{}_show'.format(indx_ch + 1)).isChecked()
            for indx_roi in range(self.num_rois):
                show_roi = getattr(self, 'checkBox_roi{}_show'.format(indx_roi + 1)).isChecked()
                for indx_hi_lo in range(2):
                    if show_ch and show_roi:
                        #print('plotting')
                        color = self.colors[indx_ch]
                        value = self.roi_values[indx_ch,indx_roi,indx_hi_lo]
                        h = self.figure_mca.ax.plot([value, value], [0, ylims[1] * 0.85], color, linestyle='dashed',
                                                        linewidth=0.5)
                        self.roi_plots.append(h)

        self.canvas_mca.draw_idle()

    def xs3_acquire(self):
        self.roi_plots = []
        print('Xspress3 acquisition starting...')
        plan = self.service_plan_funcs['xs_count']
        acq_time = self.spinBox_acq_time.value()
        self.RE(plan(acq_time = acq_time))
        self.acquired = True
        self.plot_traces()
        self.update_roi_plot()
        self.canvas_mca.draw_idle()
        print('Xspress3 acquisition complete')

    def plot_traces(self):
        #THis method plot the MCA signal
        update_figure([self.figure_mca.ax], self.toolbar_mca, self.canvas_mca)
        self.roi_plots = []
        if self.acquired:
            for indx in range(self.num_channels):
                if getattr(self, self.checkbox_ch.format(indx+1)).isChecked():
                    ch = getattr(self.xs,'mca{}'.format(indx+1))
                    mca = ch.get()
                    energy = np.array(list(range(len(mca))))*10
                    self.figure_mca.ax.plot(energy[10:],mca[10:],self.colors[indx], label = 'Channel {}'.format(indx+1))
                    self.figure_mca.ax.legend(loc=1)
        self.update_roi_plot()