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
from bluesky.callbacks import LivePlot

from ..elements.liveplots import XASPlot#, XASPlotX

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')



class UIRun(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE=None,
                 db=None,
                 scan_manager = None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.RE = RE
        self.parent = parent
        self.scan_manager = scan_manager
        self.push_run_scan.clicked.connect(self.run_scan)
        self.push_run_test_scan.clicked.connect(self.run_test_scan)
        # List with uids of scans created in the "run" mode:
        self.run_mode_uids = []
        self.rr_token = None

    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax1 = self.figure.add_subplot(111)
        self.figure.ax2 = self.figure.ax1.twinx()
        self.figure.ax3 = self.figure.ax1.twinx()
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.figure.ax3.grid(alpha = 0.4)
        self.canvas.draw_idle()

    def run_test_scan(self):
        name = self.parameter_values[0].text()
        repeats = self.parameter_values[2].value()
        self.parameter_values[0].setText(f'test {name}')
        self.parameter_values[2].setValue(1)
        self.run_scan()
        self.parameter_values[0].setText(name)
        self.parameter_values[2].setValue(repeats)

    def update_scan_defs(self, scan_defs):
        self.comboBox_scan_defs.clear()
        self.comboBox_scan_defs.addItems(scan_defs )

    def run_scan(self):
        # ignore_shutter = False
        # energy_grid = []
        # time_grid = []
        #
        # for shutter in [self.shutter_dictionary[shutter] for shutter in self.shutter_dictionary if
        #                 self.shutter_dictionary[shutter].shutter_type != 'SP']:
        #     if type(shutter.state) == str:
        #         isclosed = (shutter.state == 'closed')
        #     else:
        #         isclosed = (shutter.state.value == 1)
        #     if isclosed:
        #         ret = question_message_box(self, 'Shutter closed',
        #                                    'Would you like to run the scan with the shutter closed?')
        #         if not ret:
        #             print('Aborted!')
        #             return False
        #         ignore_shutter = True
        #         break

        name_provided = self.parameter_values[0].text()
        if name_provided:
            pass
            # timenow = datetime.datetime.now()
            # print('\nStarting scan at {}'.format(timenow.strftime("%H:%M:%S"),flush='true'))
            # start_scan_timer=timer()
            #
            # # Get parameters from the widgets and organize them in a dictionary (run_params)
            # run_parameters = return_parameters_from_widget(self.parameter_descriptions,self.parameter_values,
            #                                                 self.parameter_types)
            #
            # # Run the scan using the dict created before
            # self.run_mode_uids = []
            # self.parent.run_mode = 'run'
            # plan_key = self.comboBox_scan_type.currentText()
            #
            # if plan_key.lower().startswith('step scan'):
            #     update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)
            #     print(f'E0 {self.e0}')
            #     energy_grid, time_grid = generate_energy_grid(float(self.e0),
            #                                                   float(self.edit_preedge_start.text()),
            #                                                   float(self.edit_xanes_start.text()),
            #                                                   float(self.edit_xanes_end.text()),
            #                                                   float(self.edit_exafs_end.text()),
            #                                                   float(self.edit_preedge_spacing.text()),
            #                                                   float(self.edit_xanes_spacing.text()),
            #                                                   float(self.edit_exafs_spacing.text()),
            #                                                   float(self.edit_preedge_dwell.text()),
            #                                                   float(self.edit_xanes_dwell.text()),
            #                                                   float(self.edit_exafs_dwell.text()),
            #                                                   int(self.comboBox_exafs_dwell_kpower.currentText())
            #                                                   )
            #
            # plan_func = self.plan_funcs[plan_key]
            #
            # LivePlots = [XASPlot(self.apb.ch1_mean.name, self.apb.ch2_mean.name, 'Transmission', self.hhm[0].energy.name,
            #                        log=True, ax=self.figure.ax1, color='b', legend_keys=['Transmission']),
            #              XASPlot(self.apb.ch2_mean.name, self.apb.ch3_mean.name, 'Reference', self.hhm[0].energy.name,
            #                        log=True, ax=self.figure.ax1, color='r', legend_keys=['Reference']),
            #              XASPlot(self.apb.ch4_mean.name, self.apb.ch1_mean.name, 'Fluorescence',self.hhm[0].energy.name,
            #                      log=False,ax=self.figure.ax1, color='g', legend_keys=['Fluorescence']),
            #              ]
            # try:
            #     self.pil100k =  self.detector_dict['Pilatus 100k']['device'].stats1.total
            #
            #     if 'emission' in plan_key.lower():
            #         label = 'XES'
            #     else:
            #         label = 'HERFD'
            #     LivePlotPilatus = XASPlot(self.pil100k.name, self.apb.ch1_mean.name, label, self.hhm[0].energy.name,
            #                 log=False, ax=self.figure.ax1, color='k', legend_keys=[label])
            #
            # except:
            #     LivePlotPilatus = None
            #
            #
            # try:
            #     _xs = self.detector_dict['Xspress3']['device'].channel1.rois.roi01.value
            #     _xs_at = self.detector_dict['Xspress3']['device'].settings.acquire_time
            #     LivePlotXspress3 = XASPlot(_xs.name, self.apb.ch1_mean.name, 'SDD', self.hhm[0].energy.name,
            #                                           log=False,  ax=self.figure.ax1, color='m', legend_keys=['SDD ch1-roi1'])
            # except:
            #     LivePlotXspress3 = None
            #
            #
            # RE_args = [plan_func(**run_parameters,
            #                      ignore_shutter=ignore_shutter,
            #                      energy_grid=energy_grid,
            #                      time_grid=time_grid,
            #                      element=self.element,
            #                      e0=self.e0,
            #                      edge=self.edge,
            #                      ax=self.figure.ax1,
            #                      stdout=self.parent.emitstream_out)]
            #
            # if plan_key.lower().endswith('pilatus'):
            #     if LivePlotPilatus:
            #         LivePlots.append(LivePlotPilatus)
            #
            # if plan_key.lower().endswith('xspress 3'):
            #     if LivePlotXspress3:
            #         LivePlots.append(LivePlotXspress3)
            #
            # if plan_key.lower().startswith('step scan'):
            #     RE_args.append(LivePlots)
            #     self._save_step_scan_settings()
            #
            # self.run_mode_uids = self.RE(*RE_args)
            #
            # timenow = datetime.datetime.now()
            # print('Scan complete at {}'.format(timenow.strftime("%H:%M:%S")))
            # stop_scan_timer=timer()
            # print('Scan duration {} s'.format(stop_scan_timer-start_scan_timer))
            # if self.rr_token is not None:
            #     self.RE.unsubscribe(self.rr_token)

        else:
            message_box('Error', 'Please provide the name for the scan')



    def draw_interpolated_data(self, df):
        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)
        if 'i0' in df and 'it' in df and 'energy' in df:
            transmission = np.array(np.log(df['i0'] / df['it']))
        if 'i0' in df and 'iff' in df and 'energy' in df:
            fluorescence = np.array(df['iff'] / df['i0'])
        if 'it' in df and 'ir' in df and 'energy' in df:
            reference = np.array(np.log(df['it'] / df['ir']))

        energy = np.array(df['energy'])
        edge = int(len(energy) * 0.02)
        #print(f'Before drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
        #print(f'After drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.legend(loc=2)
        self.figure.ax2.plot(energy[edge:-edge], fluorescence[edge:-edge], color='g', label='Total fluorescence')
        self.figure.ax2.legend(loc=1)
        self.figure.ax3.plot(energy[edge:-edge], reference[edge:-edge], color='b', label='Reference')
        self.figure.ax3.legend(loc=3)
        self.canvas.draw_idle()






