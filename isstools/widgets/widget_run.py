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
                 plan_funcs=None,
                 aux_plan_funcs=None,
                 RE=None,
                 db=None,
                 hhm=None,
                 detector_dict=None,
                 shutter_dict=None,
                 motor_dict=None,
                 apb=None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        # TODO : remove hhm dependency
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = plan_funcs.keys()
        self.aux_plan_funcs = aux_plan_funcs
        self.RE = RE
        self.db = db
        self.hhm=hhm,
        self.detector_dict = detector_dict
        self.shutter_dictionary = shutter_dict
        self.motor_dictionary = motor_dict

        self.apb = apb
        self.parent = parent
        self.comboBox_scan_type.addItems(self.plan_funcs_names)
        self.comboBox_scan_type.currentIndexChanged.connect(self.populate_parameter_grid)
        self.push_run_scan.clicked.connect(self.run_scan)
        self.push_run_test_scan.clicked.connect(self.run_test_scan)

        # List with uids of scans created in the "run" mode:
        self.run_mode_uids = []
        self.rr_token = None

        self.parameter_values = []
        self.parameter_descriptions = []
        self.populate_parameter_grid(0)



        self.widget_energy_selector = widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.push_info_from_autopilot.clicked.connect(self.get_info_from_autopilot)
        self.energy_grid = []


        ## Persistance of parameters:
        self.settings = parent.settings
        self.widget_energy_selector.comboBox_element.setCurrentIndex(self.settings.value('step_element_index', defaultValue=0, type=int)) #
        self.widget_energy_selector.comboBox_edge.setCurrentIndex(self.settings.value('step_edge_index', defaultValue=0, type=int))  #
        self.edit_preedge_spacing.setText(self.settings.value('step_preedge_spacing', defaultValue='10', type=str)) #
        self.edit_xanes_spacing.setText(self.settings.value('step_xanes_spacing', defaultValue='10', type=str)) #
        self.edit_exafs_spacing.setText(self.settings.value('step_exafs_spacing', defaultValue='1', type=str)) #
        self.edit_preedge_start.setText(self.settings.value('step_preedge_start', defaultValue='-100', type=str)) #
        self.edit_xanes_start.setText(self.settings.value('step_xanes_start', defaultValue='-30', type=str)) #
        self.edit_xanes_end.setText(self.settings.value('step_xanes_end', defaultValue='30', type=str)) #
        self.edit_exafs_end.setText(self.settings.value('step_exafs_end', defaultValue='6', type=str)) #
        self.edit_preedge_dwell.setText(self.settings.value('step_preedge_dwell', defaultValue='1', type=str)) #
        self.edit_xanes_dwell.setText(self.settings.value('step_xanes_dwell', defaultValue='1', type=str))
        self.edit_exafs_dwell.setText(self.settings.value('step_exafs_dwell', defaultValue='1', type=str))
        self.comboBox_exafs_dwell_kpower.setCurrentIndex(self.settings.value('step_exafs_dwell_kpower_index', defaultValue=0, type=int))

        ## connect energy_selector layout
        self.widget_energy_selector.edit_E0.textChanged.connect(self.update_E0)
        self.widget_energy_selector.comboBox_edge.currentTextChanged.connect(self.update_edge)
        self.widget_energy_selector.comboBox_element.currentTextChanged.connect(self.update_element)

        self.element = self.widget_energy_selector.comboBox_element.currentText()
        self.edge = self.widget_energy_selector.comboBox_edge.currentText()
        self.e0 = self.widget_energy_selector.edit_E0.text()



    def _save_step_scan_settings(self):
        step_element_index = self.widget_energy_selector.comboBox_element.currentIndex()
        self.settings.setValue('step_element_index', step_element_index)
        step_edge_index = self.widget_energy_selector.comboBox_edge.currentIndex()
        self.settings.setValue('step_edge_index', step_edge_index)
        step_preedge_spacing = self.edit_preedge_spacing.text()
        self.settings.setValue('step_preedge_spacing', step_preedge_spacing)
        step_xanes_spacing = self.edit_xanes_spacing.text()
        self.settings.setValue('step_xanes_spacing', step_xanes_spacing)
        step_exafs_spacing = self.edit_exafs_spacing.text()
        self.settings.setValue('step_exafs_spacing', step_exafs_spacing)
        step_preedge_start = self.edit_preedge_start.text()
        self.settings.setValue('step_preedge_start', step_preedge_start)
        step_xanes_start = self.edit_xanes_start.text()
        self.settings.setValue('step_xanes_start', step_xanes_start)
        step_xanes_end = self.edit_xanes_end.text()
        self.settings.setValue('step_xanes_end', step_xanes_end)
        step_exafs_end = self.edit_exafs_end.text()
        self.settings.setValue('step_exafs_end', step_exafs_end)
        step_preedge_dwell = self.edit_preedge_dwell.text()
        self.settings.setValue('step_preedge_dwell', step_preedge_dwell)
        step_xanes_dwell = self.edit_xanes_dwell.text()
        self.settings.setValue('step_xanes_dwell', step_xanes_dwell)
        step_exafs_dwell = self.edit_exafs_dwell.text()
        self.settings.setValue('step_exafs_dwell', step_exafs_dwell)
        step_exafs_dwell_kpower_index = self.comboBox_exafs_dwell_kpower.currentIndex()
        self.settings.setValue('step_exafs_dwell_kpower_index', step_exafs_dwell_kpower_index)






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

    def run_scan(self):
        ignore_shutter = False
        energy_grid = []
        time_grid = []

        for shutter in [self.shutter_dictionary[shutter] for shutter in self.shutter_dictionary if
                        self.shutter_dictionary[shutter].shutter_type != 'SP']:
            if type(shutter.state) == str:
                isclosed = (shutter.state == 'closed')
            else:
                isclosed = (shutter.state.value == 1)
            if isclosed:
                ret = question_message_box(self, 'Shutter closed',
                                           'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print('Aborted!')
                    return False
                ignore_shutter = True
                break

        name_provided = self.parameter_values[0].text()
        if name_provided:
            timenow = datetime.datetime.now()
            print('\nStarting scan at {}'.format(timenow.strftime("%H:%M:%S"),flush='true'))
            start_scan_timer=timer()
            
            # Get parameters from the widgets and organize them in a dictionary (run_params)
            run_parameters = return_parameters_from_widget(self.parameter_descriptions,self.parameter_values,
                                                            self.parameter_types)

            # Run the scan using the dict created before
            self.run_mode_uids = []
            self.parent.run_mode = 'run'
            plan_key = self.comboBox_scan_type.currentText()

            if plan_key.lower().startswith('step scan'):
                update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)
                print(f'E0 {self.e0}')
                energy_grid, time_grid = generate_energy_grid(float(self.e0),
                                                              float(self.edit_preedge_start.text()),
                                                              float(self.edit_xanes_start.text()),
                                                              float(self.edit_xanes_end.text()),
                                                              float(self.edit_exafs_end.text()),
                                                              float(self.edit_preedge_spacing.text()),
                                                              float(self.edit_xanes_spacing.text()),
                                                              float(self.edit_exafs_spacing.text()),
                                                              float(self.edit_preedge_dwell.text()),
                                                              float(self.edit_xanes_dwell.text()),
                                                              float(self.edit_exafs_dwell.text()),
                                                              int(self.comboBox_exafs_dwell_kpower.currentText())
                                                              )

            plan_func = self.plan_funcs[plan_key]


            _scanning_motor = 'hhm'

            try:
                self.pil100k =  self.detector_dict['Pilatus 100k']['device'].stats1.total

                if 'emission' in plan_key.lower():
                    label = 'XES'
                    _scanning_motor = 'emission'
                    LivePlotPilatus = XASPlot(self.pil100k.name, self.apb.ch1_mean.name, label, self.motor_dictionary['motor_emission']['object'].energy.name,
                                              log=False, ax=self.figure.ax1, color='k', legend_keys=[label])

                else:
                    label = 'HERFD'
                    LivePlotPilatus = XASPlot(self.pil100k.name, self.apb.ch1_mean.name, label, self.hhm[0].energy.name,
                                log=False, ax=self.figure.ax1, color='k', legend_keys=[label])

            except:
                LivePlotPilatus = None


            try:
                _xs = self.detector_dict['Xspress3']['device'].channel1.rois.roi01.value
                _xs_at = self.detector_dict['Xspress3']['device'].settings.acquire_time
                # self.motor_dictionary['motor_emission']['name']
                LivePlotXspress3 = XASPlot(_xs.name, self.apb.ch1_mean.name, 'SDD', self.hhm[0].energy.name,
                                                      log=False,  ax=self.figure.ax1, color='m', legend_keys=['SDD ch1-roi1'])
            except:
                LivePlotXspress3 = None

            if _scanning_motor == 'hhm':
                LivePlots = [
                    XASPlot(self.apb.ch1_mean.name, self.apb.ch2_mean.name, 'Transmission', self.hhm[0].energy.name,
                            log=True, ax=self.figure.ax1, color='b', legend_keys=['Transmission']),
                    XASPlot(self.apb.ch2_mean.name, self.apb.ch3_mean.name, 'Reference', self.hhm[0].energy.name,
                            log=True, ax=self.figure.ax1, color='r', legend_keys=['Reference']),
                    XASPlot(self.apb.ch4_mean.name, self.apb.ch1_mean.name, 'Fluorescence', self.hhm[0].energy.name,
                            log=False, ax=self.figure.ax1, color='g', legend_keys=['Fluorescence']),
                    ]
            else:
                LivePlots = []



            RE_args = [plan_func(**run_parameters,
                                 ignore_shutter=ignore_shutter,
                                 energy_grid=energy_grid,
                                 time_grid=time_grid,
                                 element=self.element,
                                 e0=self.e0,
                                 edge=self.edge,
                                 ax=self.figure.ax1,
                                 stdout=self.parent.emitstream_out)]

            if plan_key.lower().endswith('pilatus'):
                if LivePlotPilatus:
                    LivePlots.append(LivePlotPilatus)

            if plan_key.lower().endswith('xspress 3'):
                if LivePlotXspress3:
                    LivePlots.append(LivePlotXspress3)

            if plan_key.lower().startswith('step scan'):
                RE_args.append(LivePlots)
                self._save_step_scan_settings()

            self.run_mode_uids = self.RE(*RE_args)

            timenow = datetime.datetime.now()
            print('Scan complete at {}'.format(timenow.strftime("%H:%M:%S")))
            stop_scan_timer=timer()
            print('Scan duration {} s'.format(stop_scan_timer-start_scan_timer))
            if self.rr_token is not None:
                self.RE.unsubscribe(self.rr_token)

        else:
            message_box('Error', 'Please provide the name for the scan')

    def populate_parameter_grid(self, index):
        for i in range(len(self.parameter_values)):
            self.gridLayout_parameters.removeWidget(self.parameter_values[i])
            self.gridLayout_parameters.removeWidget(self.parameter_descriptions[i])
            self.parameter_values[i].deleteLater()
            self.parameter_descriptions[i].deleteLater()

        plan_key = self.comboBox_scan_type.currentText()
        plan_func = self.plan_funcs[plan_key]
        [self.parameter_values, self.parameter_descriptions, self.parameter_types] = parse_plan_parameters(plan_func)

        for i in range(len(self.parameter_values)):
            self.gridLayout_parameters.addWidget(self.parameter_values[i], i, 0, QtCore.Qt.AlignTop)
            self.gridLayout_parameters.addWidget(self.parameter_descriptions[i], i, 1, QtCore.Qt.AlignTop)

        if plan_key.lower().startswith('step scan') and (not 'emission' in plan_key.lower()):
            self.groupBox_stepscan.setEnabled(True)
        else:
            self.groupBox_stepscan.setEnabled(False)

        if plan_key.lower().startswith('johann emission'):
            motor_emission = self.motor_dictionary['motor_emission']['object']
            if motor_emission._initialized:
                self.push_run_scan.setEnabled(True)
                self.push_run_test_scan.setEnabled(True)
                self.parameter_values[4].setValue(motor_emission.energy.limits[0])
                self.parameter_values[5].setValue(motor_emission.energy.limits[1])
            else:
                self.push_run_scan.setEnabled(False)
                self.push_run_test_scan.setEnabled(False)
        else:
            self.push_run_scan.setEnabled(True)
            self.push_run_test_scan.setEnabled(True)

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

    def update_E0(self, text):
        self.e0 = text
        # print('saving settings')
        self._save_step_scan_settings()

    def update_edge(self, text):
        # print(text)
        self.edge = text
        # self._save_step_scan_settings()

    def update_element(self, text):
        self.element = text
        # self._save_step_scan_settings()

    def get_info_from_autopilot(self):
        sample_df =  self.parent.widget_batch_mode.widget_autopilot.sample_df
        sample_number = self.comboBox_autopilot_sample_number.currentIndex()
        # name = sample_df.iloc[sample_number]['Sample label']
        name = sample_df.iloc[sample_number]['Name']
        comment = sample_df.iloc[sample_number]['Composition'] + ' ' + sample_df.iloc[sample_number]['Comment']
        name = name.replace('/','_')
        self.parameter_values[0].setText(name)
        self.parameter_values[1].setText(comment)



