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



ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')

class XASPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, *args, **kwargs):
        super().__init__(result_name, x=motor, *args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.result_name = result_name

    def event(self, doc):
        print(f' Numerator {self.num_name}')
        print(f' Denominator {self.den_name}')

        doc = dict(doc)
        doc['data'] = dict(doc['data'])
        print(doc['data'])
        try:
            if self.den_name == '1':
                denominator = 1
            else:
                denominator = doc['data'][self.den_name]
            doc['data'][self.result_name] = (doc['data'][self.num_name] / denominator)
        except KeyError:
            print('Key error')
        print(f"after normalizing:\n{doc['data']}")
        super().event(doc)



class UIRun(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 aux_plan_funcs,
                 RE,
                 db,
                 hhm,
                 shutter_dictionary,
                 adc_list,
                 enc_list,
                 xia,
                 apb,
                 parent_gui,

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
        self.shutter_dictionary = shutter_dictionary
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia
        self.apb = apb
        self.parent_gui = parent_gui
        self.comboBox_scan_type.addItems(self.plan_funcs_names)
        self.comboBox_scan_type.currentIndexChanged.connect(self.populate_parameter_grid)
        self.run_start.clicked.connect(self.run_scan)
        # List with uids of scans created in the "run" mode:
        self.run_mode_uids = []
        self.rr_token = None

        self.parameter_values = []
        self.parameter_descriptions = []
        self.populate_parameter_grid(0)

        self.element = 'Scandium (21)'
        self.e0 = '4492'
        self.edge = 'K'

        self.widget_energy_selector = widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector.addWidget(self.widget_energy_selector)
        self.widget_energy_selector.edit_E0.textChanged.connect(self.update_E0)
        self.widget_energy_selector.comboBox_edge.currentTextChanged.connect(self.update_edge)
        self.widget_energy_selector.comboBox_element.currentTextChanged.connect(self.update_element)

        self.energy_grid = []


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

    def run_scan(self):

        ignore_shutter = False
        energy_grid = []
        time_grid = []

        for shutter in [self.shutter_dictionary[shutter] for shutter in self.shutter_dictionary if
                        self.shutter_dictionary[shutter].shutter_type != 'SP']:
            if shutter.state.value:
                ret = question_message_box(self,'Shutter closed',
                                           'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print('Aborted!')
                    return False
                ignore_shutter=True
                break

        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.analog_samp_time) / self.adc_list[0].sample_rate.get() * 100000))

        for adc in self.adc_list:
            adc.averaging_points.put(str(value))

        for enc in self.enc_list:
            enc.filter_dt.put(float(self.enc_samp_time) * 100000)

        # not needed at QAS this is a detector
        if self.xia is not None:
            if self.xia.input_trigger is not None:
                self.xia.input_trigger.unit_sel.put(1)  # ms, not us
                self.xia.input_trigger.period_sp.put(int(self.xia_samp_time))

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
            self.parent_gui.run_mode = 'run'
            plan_key = self.comboBox_scan_type.currentText()

            if plan_key == 'Step scan':
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

            LivePlots = [XASPlot(self.apb.ch2_mean.name, self.apb.ch1_mean.name, 'Abs',self.hhm[0].energy.name, ax=self.figure.ax1,color='b'),
                         XASPlot(self.apb.ch2_mean.name, self.apb.ch3_mean.name, 'Ref',self.hhm[0].energy.name, ax=self.figure.ax2, color='r')]
            self.run_mode_uids = self.RE(plan_func(**run_parameters,
                                                  ax=self.figure.ax1,
                                                  ignore_shutter=ignore_shutter,
                                                  energy_grid=energy_grid,
                                                  time_grid=time_grid,
                                                  e0 =  self.e0,
                                                  edge =  self.edge,
                                                  element = self.element,
                                                  stdout=self.parent_gui.emitstream_out),LivePlots
                                         )
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

        plan_func = self.plan_funcs[self.comboBox_scan_type.currentText()]
        [self.parameter_values, self.parameter_descriptions, self.parameter_types] = parse_plan_parameters(plan_func)

        for i in range(len(self.parameter_values)):
            self.gridLayout_parameters.addWidget(self.parameter_values[i], i, 0, QtCore.Qt.AlignTop)
            self.gridLayout_parameters.addWidget(self.parameter_descriptions[i], i, 1, QtCore.Qt.AlignTop)

    def setAnalogSampTime(self, text):
        self.analog_samp_time = text

    def setEncSampTime(self, text):
        self.enc_samp_time = text

    def setXiaSampTime(self, text):
        self.xia_samp_time = text

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

        self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
        self.figure.ax1.legend(loc=2)
        self.figure.ax2.plot(energy[edge:-edge], fluorescence[edge:-edge], color='g', label='Total fluorescence')
        self.figure.ax2.legend(loc=1)
        self.figure.ax3.plot(energy[edge:-edge], reference[edge:-edge], color='b', label='Reference')
        self.figure.ax3.legend(loc=3)
        self.canvas.draw_idle()

    def update_E0(self, text):
        self.e0 = text

    def update_edge(self, text):
        self.edge = text

    def update_element(self, text):
        self.element = text