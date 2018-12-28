import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure
from isstools.elements.parameter_handler import parse_plan_parameters, return_parameters_from_widget
from isstools.xasdata.xasdata import XASdataGeneric

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')

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
        self.shutter_dictionary = shutter_dictionary
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia
        self.gen_parser = XASdataGeneric(hhm.enc.pulses_per_deg, db)
        self.parent_gui = parent_gui
        self.comboBox_scan_type.addItems(self.plan_funcs_names)
        self.comboBox_scan_type.currentIndexChanged.connect(self.populate_parameter_grid)
        self.run_start.clicked.connect(self.run_scan)
        # List with uids of scans created in the "run" mode:
        self.run_mode_uids = []

        self.parameter_values = []
        self.parameter_descriptions = []
        self.populate_parameter_grid(0)

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
        ignore_shutter=False

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
        value = int(round(float(self.analog_samp_time) / self.adc_list[0].sample_rate.value * 100000))

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
            print('\nStarting scan at {}'.format(timenow.strftime("%H:%M:%S")))
            start_scan_timer=timer()
            
            # Get parameters from the widgets and organize them in a dictionary (run_params)
            run_parameters = return_parameters_from_widget(self.parameter_descriptions,self.parameter_values,
                                                            self.parameter_types)
            print(run_parameters)
            # Run the scan using the dict created before
            self.run_mode_uids = []
            self.parent_gui.run_mode = 'run'
            plan_key = self.comboBox_scan_type.currentText()
            plan_func = self.plan_funcs[plan_key]
            self.run_mode_uids = self.RE(plan_func(**run_parameters,
                                                   ax=self.figure.ax1,
                                                   ignore_shutter=ignore_shutter,
                                                   stdout=self.parent_gui.emitstream_out))
            timenow = datetime.datetime.now()
            print('Scan complete at {}'.format(timenow.strftime("%H:%M:%S")))
            stop_scan_timer=timer()
            print('Scan duration {}'.format(stop_scan_timer-start_scan_timer))


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

    def draw_func(self, df):
        if 'i0' in df and 'it' in df and 'energy' in df:
            transmission = np.array(df['i0'] / df['it'])

        energy = np.array(df['energy'])
        edge = int(len(energy) * 0.02)

        self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
        self.figure.ax1.legend(loc=1)
        self.canvas.draw_idle()



    def plot_scan(self, data):
        if self.parent_gui.run_mode == 'run':
            update_figure([self.figure.ax2,self.figure.ax1, self.figure.ax3],self.toolbar,self.canvas)

            df = data['processing_ret']['data']
            if isinstance(df, str):
                df = self.gen_parser.getInterpFromFile(df)
            df = df.sort_values('energy')
            self.df = df

            if 'i0' in df and 'it' in df and 'energy' in df:
                self.transmission = transmission = np.array(np.log(df['i0']/df['it']))
            else:
                print("Warning, could not find 'i0', 'it', or 'energy' (are devices present?)")

            if 'i0' in df and 'iff' in df and 'energy' in df:
                fluorescence = np.array(df['iff']/df['i0'])

            if 'it' in df and 'ir' in df and 'energy' in df:
                reference = np.array(np.log(df['it']/df['ir']))

            energy =  np.array(df['energy'])

            edge=int(len(energy)*0.02)

            self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
            self.figure.ax1.legend(loc=1)
            self.figure.ax2.plot(energy[edge:-edge], fluorescence[edge:-edge], color='g',label='Total fluorescence')
            self.figure.ax2.legend(loc=2)
            self.figure.ax3.plot(energy[edge:-edge], reference[edge:-edge], color='b',label='Reference')
            self.figure.ax3.legend(loc=3)
            self.canvas.draw_idle()
            self.aux_plan_funcs['write_html_log'](uid, figure)
