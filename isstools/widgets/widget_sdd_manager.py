import re
import time as ttime

import numpy as np
import pkg_resources

from PyQt5 import uic
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor

from isstools.xiaparser import xiaparser
from isstools.elements.figure_update import update_figure


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sdd_manager.ui')


class UISDDManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 xia_list=[],
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.xia_list = xia_list
        self.xia_parser = xiaparser.xiaparser()
        self.xia_graphs_names = []
        self.xia_graphs_labels = []
        self.xia_handles = []



        self.xia = self.xia_list[0]
        self.xia_channels = [int(mca.split('mca')[1]) for mca in
                             set(self.xia.read_attrs) & set(self.xia.component_names)]
        self.xia_tog_channels = []

        self.xia.mca_max_energy.subscribe(self.update_xia_params)
        self.xia.real_time.subscribe(self.update_xia_params)
        self.xia.real_time_rb.subscribe(self.update_xia_params)
        self.edit_xia_acq_time.returnPressed.connect(self.update_xia_acqtime_pv)
        self.edit_xia_energy_range.returnPressed.connect(self.update_xia_energyrange_pv)
        self.push_gain_matching.clicked.connect(self.run_gain_matching)

        self.push_run_xia_measurement.clicked.connect(self.update_xia_rois)
        self.push_run_xia_measurement.clicked.connect(self.start_xia_spectra)
        if self.xia.connected:
            max_en = self.xia.mca_max_energy.value
            energies = np.linspace(0, max_en, 2048)
    
            self.roi_colors = []
            for mult in range(4):
                self.roi_colors.append((.4 + (.2 * mult), 0, 0))
                self.roi_colors.append((0, .4 + (.2 * mult), 0))
                self.roi_colors.append((0, 0, .4 + (.2 * mult)))
    
            for roi in range(12):
                low = getattr(self.xia, "mca1.roi{}".format(roi)).low.value
                high = getattr(self.xia, "mca1.roi{}".format(roi)).high.value
                if low > 0:
                    getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(
                        np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).low.value] * 1000)))
                else:
                    getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(low))
                if high > 0:
                    getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(
                        np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).high.value] * 1000)))
                else:
                    getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(high))
    
                label = getattr(self.xia, "mca1.roi{}".format(roi)).label.value
                getattr(self, 'edit_roi_name_{}'.format(roi)).setText(label)
    
                getattr(self, 'edit_roi_from_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                getattr(self, 'edit_roi_to_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                getattr(self, 'edit_roi_name_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
    
    
            for channel in self.xia_channels:
                getattr(self, "checkBox_gm_ch{}".format(channel)).setEnabled(True)
                getattr(self.xia, "mca{}".format(channel)).array.subscribe(self.update_xia_graph)
                getattr(self, "checkBox_gm_ch{}".format(channel)).toggled.connect(self.toggle_xia_checkbox)
            self.push_checkall_xia.clicked.connect(self.toggle_xia_all)
    
            if hasattr(self.xia, 'input_trigger'):
                if self.xia.input_trigger is not None:
                    self.xia.input_trigger.unit_sel.put(1)  # ms, not us

    def addCanvas(self):
        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='#FcF9F6')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.figure_gain_matching.ax = self.figure_gain_matching.add_subplot(111)
        self.toolbar_gain_matching = NavigationToolbar(self.canvas_gain_matching, self, coordinates=True)
        self.plot_gain_matching.addWidget(self.toolbar_gain_matching)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw_idle()

        self.figure_xia_all_graphs = Figure()
        self.figure_xia_all_graphs.set_facecolor(color='#FcF9F6')
        self.canvas_xia_all_graphs = FigureCanvas(self.figure_xia_all_graphs)
        self.figure_xia_all_graphs.ax = self.figure_xia_all_graphs.add_subplot(111)
        self.toolbar_xia_all_graphs = NavigationToolbar(self.canvas_xia_all_graphs, self, coordinates=True)
        self.plot_xia_all_graphs.addWidget(self.toolbar_xia_all_graphs)
        self.plot_xia_all_graphs.addWidget(self.canvas_xia_all_graphs)
        self.canvas_xia_all_graphs.draw_idle()
        self.cursor_xia_all_graphs = Cursor(self.figure_xia_all_graphs.ax, useblit=True, color='green', linewidth=0.75)
        self.figure_xia_all_graphs.ax.clear()

    def toggle_xia_checkbox(self, value):
        if value:
            self.xia_tog_channels.append(self.sender().text())
        elif self.sender().text() in self.xia_tog_channels:
            self.xia_tog_channels.remove(self.sender().text())
        self.erase_xia_graph()
        for chan in self.xia_tog_channels:
            self.update_xia_graph(getattr(self.xia, 'mca{}.array.value'.format(chan)),
                                  obj=getattr(self.xia, 'mca{}.array'.format(chan)))

    def toggle_xia_all(self):
        if len(self.xia_tog_channels) != len(self.xia.read_attrs):
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(True)
        else:
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(False)

    def update_xia_params(self, value, **kwargs):
        if kwargs['obj'].name == 'xia1_real_time':
            self.edit_xia_acq_time.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_real_time_rb':
            self.label_acq_time_rbv.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_mca_max_energy':
            self.edit_xia_energy_range.setText('{:.0f}'.format(value * 1000))

    def erase_xia_graph(self):
        self.figure_xia_all_graphs.ax.clear()

        for roi in range(12):
            if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                    self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))


        self.figure_xia_all_graphs.ax.clear()
        self.toolbar_xia_all_graphs.update()
        self.xia_graphs_names.clear()
        self.xia_graphs_labels.clear()
        self.xia_handles.clear()
        self.canvas_xia_all_graphs.draw_idle()

    def start_xia_spectra(self):
        if self.xia.collect_mode.value != 0:
            self.xia.collect_mode.put(0)
            ttime.sleep(2)
        self.xia.erase_start.put(1)

    def update_xia_rois(self):
        energies = np.linspace(0, float(self.edit_xia_energy_range.text()) / 1000, 2048)

        for roi in range(12):
            if float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) < 0 or float(
                    getattr(self, 'edit_roi_to_{}'.format(roi)).text()) < 0:
                exec('start{} = -1'.format(roi))
                exec('end{} = -1'.format(roi))
            else:
                indexes_array = np.where(
                    (energies >= float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) / 1000) & (
                    energies <= float(getattr(self, 'edit_roi_to_{}'.format(roi)).text()) / 1000) == True)[0]
                if len(indexes_array):
                    exec('start{} = indexes_array.min()'.format(roi))
                    exec('end{} = indexes_array.max()'.format(roi))
                else:
                    exec('start{} = -1'.format(roi))
                    exec('end{} = -1'.format(roi))
            exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi, roi,
                                                                                                            roi))
            exec('label{} = self.edit_roi_name_{}.text()'.format(roi, roi))

        for channel in self.xia_channels:
            for roi in range(12):
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).low.put(eval('start{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).high.put(eval('end{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).label.put(eval('label{}'.format(roi)))

        for roi in range(12):
            if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                        roi, roi))
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                        roi, roi))

            else:
                exec('self.figure_xia_all_graphs.ax.roi{}l.set_xdata([roi{}x[0], roi{}x[0]])'.format(roi, roi, roi))
                exec('self.figure_xia_all_graphs.ax.roi{}h.set_xdata([roi{}x[1], roi{}x[1]])'.format(roi, roi, roi))

        self.figure_xia_all_graphs.ax.grid(True)
        self.canvas_xia_all_graphs.draw_idle()

    def update_xia_acqtime_pv(self):
        self.xia.real_time.put(float(self.edit_xia_acq_time.text()))

    def update_xia_energyrange_pv(self):
        self.xia.mca_max_energy.put(float(self.edit_xia_energy_range.text()) / 1000)

    def update_xia_graph(self, value, **kwargs):
        curr_name = kwargs['obj'].name
        curr_index = -1
        if len(self.figure_xia_all_graphs.ax.lines):
            if float(self.edit_xia_energy_range.text()) != self.figure_xia_all_graphs.ax.lines[0].get_xdata()[-1]:
                self.figure_xia_all_graphs.ax.clear()
                for roi in range(12):
                    if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                            self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))


                update_figure([self.figure_xia_all_graphs.ax], self.toolbar_xia_all_graphs, self.canvas_xia_all_graphs)

                self.xia_graphs_names.clear()
                self.xia_graphs_labels.clear()
                self.canvas_xia_all_graphs.draw_idle()

        if curr_name in self.xia_graphs_names:
            for index, name in enumerate(self.xia_graphs_names):
                if curr_name == name:
                    curr_index = index
                    line = self.figure_xia_all_graphs.ax.lines[curr_index]
                    line.set_ydata(value)
                    break

        else:
            ch_number = curr_name.split('_')[1].split('mca')[1]
            if ch_number in self.xia_tog_channels:
                self.xia_graphs_names.append(curr_name)
                label = 'Chan {}'.format(ch_number)
                self.xia_graphs_labels.append(label)
                handles, = self.figure_xia_all_graphs.ax.plot(
                    np.linspace(0, float(self.edit_xia_energy_range.text()), 2048), value, label=label)
                self.xia_handles.append(handles)
                self.figure_xia_all_graphs.ax.legend(self.xia_handles, self.xia_graphs_labels)

            if len(self.figure_xia_all_graphs.ax.lines) == len(self.xia_tog_channels) != 0:
                for roi in range(12):
                    exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi,
                                                                                                                    roi,
                                                                                                                    roi))

                for roi in range(12):
                    if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                                roi, roi))
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                                roi, roi))

                self.figure_xia_all_graphs.ax.grid(True)

        self.figure_xia_all_graphs.ax.relim()
        self.figure_xia_all_graphs.ax.autoscale(True, True, True)
        y_interval = self.figure_xia_all_graphs.ax.get_yaxis().get_data_interval()
        '''
        if len(y_interval):
            if y_interval[0] != 0 or y_interval[1] != 0:
                self.figure_xia_all_graphs.ax.set_ylim([y_interval[0] - (y_interval[1] - y_interval[0]) * 0.05,
                                                        y_interval[1] + (y_interval[1] - y_interval[0]) * 0.05])
        '''
        self.canvas_xia_all_graphs.draw_idle()

    def run_gain_matching(self):
        ax = self.figure_gain_matching.add_subplot(111)
        gain_adjust = [0.001] * len(self.xia_channels)  # , 0.001, 0.001, 0.001]
        diff = [0] * len(self.xia_channels)  # , 0, 0, 0]
        diff_old = [0] * len(self.xia_channels)  # , 0, 0, 0]

        # Run number of iterations defined in the text edit edit_gain_matching_iterations:
        for i in range(int(self.edit_gain_matching_iterations.text())):
            self.xia.collect_mode.put('MCA spectra')
            ttime.sleep(0.25)
            self.xia.mode.put('Real time')
            ttime.sleep(0.25)
            self.xia.real_time.put('1')
            self.xia.capt_start_stop.put(1)
            ttime.sleep(0.05)
            self.xia.erase_start.put(1)
            ttime.sleep(2)
            ax.clear()
            self.toolbar_gain_matching.update()

            # For each channel:
            for chann in self.xia_channels:
                # If checkbox of current channel is checked:
                if getattr(self, "checkBox_gm_ch{}".format(chann)).checkState() > 0:

                    # Get current channel pre-amp gain:
                    curr_ch_gain = getattr(self.xia, "pre_amp_gain{}".format(chann))

                    coeff = self.xia_parser.gain_matching(self.xia, self.edit_center_gain_matching.text(),
                                                          self.edit_range_gain_matching.text(), chann, ax)
                    # coeff[0] = Intensity
                    # coeff[1] = Fitted mean
                    # coeff[2] = Sigma

                    diff[chann - 1] = float(self.edit_gain_matching_target.text()) - float(coeff[1] * 1000)

                    if i != 0:
                        sign = (diff[chann - 1] * diff_old[chann - 1]) / math.fabs(
                            diff[chann - 1] * diff_old[chann - 1])
                        if int(sign) == -1:
                            gain_adjust[chann - 1] /= 2
                    print('Chan ' + str(chann) + ': ' + str(diff[chann - 1]) + '\n')

                    # Update current channel pre-amp gain:
                    curr_ch_gain.put(curr_ch_gain.value - diff[chann - 1] * gain_adjust[chann - 1])
                    diff_old[chann - 1] = diff[chann - 1]

                    self.canvas_gain_matching.draw_idle()
