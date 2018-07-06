import pkg_resources
import inspect
import re
import os
from subprocess import call
from PyQt5 import uic, QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import time as ttime
import numpy as np
import datetime
from timeit import default_timer as timer



# Libs needed by the ZMQ communication
import json
import pandas as pd

timenow = datetime.datetime.now()

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')

from isstools.xiaparser import xiaparser
from isstools.xasdata.xasdata import XASdataGeneric

class UIRun(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 RE,
                 db,
                 shutters,
                 adc_list,
                 enc_list,
                 xia,
                 html_log_func,
                 parent_gui,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        # TODO : remove hhm dependency
        self.gen_parser = XASdataGeneric(parent_gui.hhm.enc.pulses_per_deg, db)

        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.RE = RE
        self.db = db
        if self.db is None:
            self.run_start.setEnabled(False)

        self.shutters = shutters
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia
        self.html_log_func = html_log_func
        self.parent_gui = parent_gui

        self.filepaths = []
        self.xia_parser = xiaparser.xiaparser()

        self.run_type.addItems(self.plan_funcs_names)
        self.run_start.clicked.connect(self.run_scan)

        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)

        self.run_type.currentIndexChanged.connect(self.populateParams)

        # List with uids of scans created in the "run" mode:
        self.run_mode_uids = []

        self.params1 = []
        self.params2 = []
        self.params3 = []
        if len(self.plan_funcs) != 0:
            self.populateParams(0)

    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax1 = self.figure.add_subplot(111)

        self.figure.ax2 = self.figure.ax1.twinx()
        self.figure.ax3 = self.figure.ax1.twinx()
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.figure.ax3.grid(alpha = 0.4)
        self.canvas.draw_idle()

    def run_scan(self):
        ignore_shutter=False
        if self.run_type.currentText() == 'get_offsets':
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'PH' and
                                            self.shutters[shutter].state.read()['{}_state'.format(shutter)][
                                                'value'] != 1]:
                shutter.close()
                while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                    QtWidgets.QApplication.processEvents()
                    ttime.sleep(0.1)

        else:
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type != 'SP']:
                if shutter.state.value:
                    ret = self.questionMessage('Shutter closed',
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

        self.comment = self.params2[0].text()
        if (self.comment):
            timenow = datetime.datetime.now()
            print('\nStarting scan at {}'.format(timenow.strftime("%H:%M:%S")))
            start_scan_timer=timer()
            
            # Get parameters from the widgets and organize them in a dictionary (run_params)
            run_params = {}
            for i in range(len(self.params1)):
                if (self.param_types[i] == int):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == float):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == bool):
                    run_params[self.params3[i].text().split('=')[0]] = bool(self.params2[i].checkState())
                elif (self.param_types[i] == str):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].text()

            # Erase last graph
            self.figure.ax1.clear()
            self.figure.ax2.clear()
            self.figure.ax3.clear()
            self.toolbar.update()
            self.canvas.draw_idle()
            self.figure.ax3.grid(alpha = 0.4)
            
            # Run the scan using the dict created before
            self.run_mode_uids = []
            self.parent_gui.run_mode = 'run'
            self.run_mode_uids = self.RE(self.plan_funcs[self.run_type.currentIndex()](**run_params,
                                                                                  ax=self.figure.ax1,
                                                                                  ignore_shutter=ignore_shutter,
                                                                                  stdout=self.parent_gui.emitstream_out))
            timenow = datetime.datetime.now()
            print('Scan complete at {}'.format(timenow.strftime("%H:%M:%S")))
            stop_scan_timer=timer()  
            print('Scan duration {}'.format(stop_scan_timer-start_scan_timer))

        else:
            print('\nPlease, type the name of the scan in the field "name"\nTry again')

    def show_scan_help(self):
        title = self.run_type.currentText()
        message = self.plan_funcs[self.run_type.currentIndex()].__doc__
        QtWidgets.QMessageBox.question(self,
                                       'Help! - {}'.format(title),
                                       message,
                                       QtWidgets.QMessageBox.Ok)

    def create_log_scan(self, uid, figure):
        self.canvas.draw_idle()
        if self.html_log_func is not None:
            self.html_log_func(uid, figure)

    def populateParams(self, index):
        for i in range(len(self.params1)):
            self.gridLayout_13.removeWidget(self.params1[i])
            self.gridLayout_13.removeWidget(self.params2[i])
            self.gridLayout_13.removeWidget(self.params3[i])
            self.params1[i].deleteLater()
            self.params2[i].deleteLater()
            self.params3[i].deleteLater()
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.param_types = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default,
                                 signature.parameters[list(signature.parameters)[i]].annotation,
                                 grid=self.gridLayout_13, params=[self.params1, self.params2, self.params3])
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def addParamControl(self, name, default, annotation, grid, params):
        rows = int((grid.count()) / 3)
        param1 = QtWidgets.QLabel(str(rows + 1))

        param2 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtWidgets.QSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtWidgets.QDoubleSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtWidgets.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        elif annotation == str:
            param2 = QtWidgets.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        if param2 is not None:
            param3 = QtWidgets.QLabel(default)
            grid.addWidget(param1, rows, 0, QtCore.Qt.AlignTop)
            grid.addWidget(param2, rows, 1, QtCore.Qt.AlignTop)
            grid.addWidget(param3, rows, 2, QtCore.Qt.AlignTop)
            params[0].append(param1)
            params[1].append(param2)
            params[2].append(param3)

    def questionMessage(self, title, question):
        reply = QtWidgets.QMessageBox.question(self, title,
                                               question,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            return True
        elif reply == QtWidgets.QMessageBox.No:
            return False
        else:
            return False

    def setAnalogSampTime(self, text):
        self.analog_samp_time = text

    def setEncSampTime(self, text):
        self.enc_samp_time = text

    def setXiaSampTime(self, text):
        self.xia_samp_time = text

    def plot_scan(self, data):
        if self.parent_gui.run_mode == 'run':
            self.figure.ax1.clear()
            self.figure.ax2.clear()
            self.figure.ax3.clear()
            self.figure.ax3.grid(alpha = 0.4)
            #self.toolbar._views.clear()
            #self.toolbar._positions.clear()
            #self.toolbar._update_view()

            df = data['processing_ret']['data']
            if isinstance(df, str):
                # load data, it's  astring
                df = self.gen_parser.getInterpFromFile(df)
            #df = pd.DataFrame.from_dict(json.loads(data['processing_ret']['data']))
            df = df.sort_values('energy')
            self.df = df

            # TODO : this should plot depending on options set in a GUI
            if 'i0' in df and 'it' in df and 'energy' in df:
                transmission = np.log(df['i0']/df['it'])
                self.figure.ax1.plot(df['energy'], transmission, color='r')
            else:
                print("Warning, could not find 'i0', 'it', or 'energy' (are devices present?)")

            if 'i0' in df and 'iff' in df and 'energy' in df:
                fluorescence = (df['iff']/df['i0'])
                self.figure.ax2.plot(df['energy'], fluorescence, color='g')

            
            if 'it' in df and 'ir' in df and 'energy' in df:
                reference = np.log(df['it']/df['ir'])
                self.figure.ax3.plot(df['energy'], reference, color='b')

            self.canvas.draw_idle()

            self.create_log_scan(data['uid'], self.figure)
