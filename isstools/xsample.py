import os
import re
import sys
import time as ttime
import matplotlib
matplotlib.use('WXAgg')
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pkg_resources
from PyQt5 import QtGui, QtWidgets, QtCore, uic
from PyQt5.Qt import QSplashScreen, QObject
from PyQt5.QtCore import QSettings, QThread, pyqtSignal, QTimer, QDateTime
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
import bluesky.plan_stubs as bps

from matplotlib.figure import Figure
from isstools.elements.figure_update import update_figure
from datetime import timedelta, datetime
import time as ttime
from .dialogs.BasicDialogs import message_box

ui_path = pkg_resources.resource_filename('isstools', 'ui/xsample.ui')

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()


# gui_form = uic.loadUiType(ui_path)[0]  # Load the UI

class XsampleGui(*uic.loadUiType(ui_path)):

    # class GUI(QtWidgets.QMainWindow, gui_form):
    def __init__(self,
                 mfcs = [],
                 rga_channels = [],
                 rga_masses = [],
                 temps = [],
                 temps_sp = [],
                 RE = [],
                 archiver = [],
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()
        self.mfcs = mfcs
        self.rga_channels = rga_channels
        self.rga_masses = rga_masses
        self.temps = temps
        self.temps_sp = temps_sp
        self.RE = RE
        self.archiver = archiver
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(2000)
        self.timer_update_time.timeout.connect(self.update_status)
        self.timer_update_time.start()

        self.timer_program = QtCore.QTimer(self)
        self.timer_program.setInterval(1000)
        self.timer_program.timeout.connect(self.update_temp_sp)


        self.push_temperature_program.clicked.connect(self.temperature_program)

        self.spinBox_CH4.valueChanged.connect(self.set_mfc_cart_flow)
        self.spinBox_CO.valueChanged.connect(self.set_mfc_cart_flow)
        self.spinBox_H2.valueChanged.connect(self.set_mfc_cart_flow)

        self.spinBox_CH4.setValue(mfcs[0].flow.get_setpoint())
        self.spinBox_CO.setValue(mfcs[1].flow.get_setpoint())
        self.spinBox_H2.setValue(mfcs[2].flow.get_setpoint())

        for indx in range(8):
            getattr(self, f'checkBox_rga{indx+1}').toggled.connect(self.update_status)


        for indx, rga_mass in enumerate(self.rga_masses):
            getattr(self, f'spinBox_rga_mass{indx + 1}').setValue(rga_mass.get())
            getattr(self, f'spinBox_rga_mass{indx + 1}').valueChanged.connect(self.change_rga_mass)

        self.tableWidget_program.setColumnCount(2)
        self.tableWidget_program.setRowCount(10)
        self.tableWidget_program.setHorizontalHeaderLabels(('Temperature\n setpoint', 'Time'))
        self.plot_program = False


    # a.setRowCount(2)
    # a.setRowCount(12)
    # a.setVerticalHeaderLabels('sd', 'sdsd')
    # a.setVerticalHeaderLabels(('sd', 'sdsd'))
    # a.setHorizontalHeaderLabels(('Temperqature setpoint', 'Time'))
    # a.setHorizontalHeaderLabels(('Temperqature\n setpoint', 'Time'))
    # a.setHorizontalHeaderLabels(('Temperature\n setpoint', 'Time'))
    # a.setHorizontalHeaderLabels(('Temperature\n setpoint', 'Time'))



    def addCanvas(self):
        self.figure_rga = Figure()
        self.figure_rga.set_facecolor(color='#FcF9F6')
        self.figure_rga.ax = self.figure_rga.add_subplot(111)
        self.canvas_rga = FigureCanvas(self.figure_rga)
        self.toolbar_rga = NavigationToolbar(self.canvas_rga, self)
        self.layout_rga.addWidget(self.canvas_rga)
        self.layout_rga.addWidget(self.toolbar_rga)
        self.canvas_rga.draw()

        self.figure_mfc = Figure()
        self.figure_mfc.set_facecolor(color='#FcF9F6')
        self.figure_mfc.ax = self.figure_mfc.add_subplot(111)
        self.canvas_mfc = FigureCanvas(self.figure_mfc)
        self.toolbar_mfc = NavigationToolbar(self.canvas_mfc, self)
        self.layout_mfc.addWidget(self.canvas_mfc)
        self.layout_mfc.addWidget(self.toolbar_mfc)
        self.canvas_mfc.draw()

        self.figure_temp = Figure()
        self.figure_temp.set_facecolor(color='#FcF9F6')
        self.figure_temp.ax = self.figure_temp.add_subplot(111)
        self.canvas_temp = FigureCanvas(self.figure_temp)
        self.toolbar_temp = NavigationToolbar(self.canvas_temp, self)
        self.layout_temp.addWidget(self.canvas_temp)
        self.layout_temp.addWidget(self.toolbar_temp)
        self.canvas_temp.draw()


    def change_rga_mass(self):
        sender_object = QObject().sender()
        indx=sender_object.objectName()[-1]
        self.RE(bps.mv(self.rga_masses[int(indx)-1],sender_object.value()))


    def update_status(self):
        if self.checkBox_update.isChecked():
            flow_CH4 = self.mfcs[0].flow.read()['mfc_cart_CH4_flow']['value']
            self.label_CH4.setText('{:.1f} sccm'.format(flow_CH4))
            flow_CO = self.mfcs[1].flow.read()['mfc_cart_CO_flow']['value']
            self.label_CO.setText('{:.1f} sccm'.format(flow_CO))
            flow_H2 = self.mfcs[2].flow.read()['mfc_cart_H2_flow']['value']
            self.label_H2.setText('{:.1f} sccm'.format(flow_H2))

            now = ttime.time()
            timewindow = self.doubleSpinBox_timewindow.value()
            data_format= mdates.DateFormatter('%H:%M:%S')


            some_time_ago = now - 3600 * timewindow
            df = self.archiver.tables_given_times(some_time_ago, now)

            masses = []
            for rga_mass in self.rga_masses:
                masses.append(str(rga_mass.get()))


            update_figure([self.figure_rga.ax], self.toolbar_rga, self.canvas_rga)
            for rga_ch, mass in zip(self.rga_channels, masses):
                dataset = df[rga_ch.name]
                indx = rga_ch.name[-1]
                if getattr(self, f'checkBox_rga{indx}').isChecked():
                    self.figure_rga.ax.plot(dataset['time']+timedelta(hours=-4),dataset['data'], label = f'{mass} amu')
            self.figure_rga.ax.grid(alpha=0.4)
            self.figure_rga.ax.xaxis.set_major_formatter(data_format)
            self.figure_rga.ax.set_xlim(ttime.ctime(some_time_ago), ttime.ctime(now))
            self.figure_rga.ax.autoscale_view(tight=True)
            self.figure_rga.ax.set_yscale('log')
            self.figure_rga.tight_layout()
            self.figure_rga.ax.legend(loc=6)
            self.canvas_rga.draw_idle()

            update_figure([self.figure_temp.ax], self.toolbar_temp, self.canvas_temp)
            if self.radioButton_current_control.isChecked():
                dataset1 = df[self.temps[0].name]
                dataset2 = df[self.temps_sp[0].name]
            else:
                dataset1 = df[self.temps[1].name]
                dataset2 = df[self.temps_sp[1].name]

            XLIM = [dataset1['time'].iloc[0] + timedelta(hours=-4),
                    dataset1['time'].iloc[-1] + timedelta(hours=-4)]

            self.figure_temp.ax.plot(dataset1['time'] + timedelta(hours=-4), dataset1['data'], label='T readback')
            self.figure_temp.ax.plot(dataset2['time'] + timedelta(hours=-4), dataset2['data'], label='T setpoint')
            if self.plot_program:
                self.figure_temp.ax.plot(self.program_dataset['time'],
                                         self.program_dataset['data'], 'k:', label='T program')
                XLIM[1] = self.program_dataset['time'].iloc[-1]


            self.figure_temp.ax.xaxis.set_major_formatter(data_format)
            self.figure_temp.ax.set_xlim(XLIM)
            self.figure_temp.ax.relim(visible_only=True)
            self.figure_temp.ax.grid(alpha=0.4)
            self.figure_temp.ax.autoscale_view(tight=True)
            self.figure_temp.tight_layout()
            self.figure_temp.ax.legend(loc=5)
            self.canvas_temp.draw_idle()



    def set_mfc_cart_flow(self):
        sender = QObject()
        sender_object = sender.sender()
        sender_name = sender_object.objectName()
        value = sender_object.value()
        mfc_dict = {'spinBox_CH4': self.mfcs[0],
                    'spinBox_CO': self.mfcs[1],
                    'spinBox_H2': self.mfcs[2],
                    }

        mfc_dict[sender_name].flow.put(value)



    def temperature_program(self):
        print('Starting the Temperature program')
        table = self.tableWidget_program
        nrows = table.rowCount()
        times = []
        temps = []
        for i in range(nrows):
            this_time = table.item(i, 1)
            this_temp = table.item(i, 0)

            if this_time and this_temp:
                try:
                    times.append(float(this_time.text()))
                except:
                    message_box('Error','Time must be numerical' )
                    raise ValueError('time must be numerical')
                try:
                    temps.append(float(this_temp.text()))
                except:
                    message_box('Error', 'Temperature must be numerical')
                    raise ValueError('Temperature must be numerical')
                

        times = np.hstack((0, np.array(times))) * 60
        temps = np.hstack((self.temps[0].get(), np.array(temps)))
        print('times', times, 'temperatures', temps)
        self.program_time = np.arange(times[0], times[-1] + 1)
        datetimes = [datetime.fromtimestamp(i).strftime('%Y-%m-%d %H:%M:%S') for i in (ttime.time() + self.program_time)]
        self.program_sps = np.interp(self.program_time, times, temps)
        self.program_dataset = pd.DataFrame({'time' : pd.to_datetime(datetimes, format='%Y-%m-%d %H:%M:%S'),
                                             'data' : self.program_sps})

        self.plot_program = True
        self.program_idx = 0
        self.init_time = ttime.time()
        self.timer_program.start()

        # plt.figure()
        # plt.plot(times, temps, 'ko-')
        # plt.plot(time_grid, self.programs_sps, 'r.-')


        # for this_time, this_temp in zip(times, temps):
        #     self.init_time = ttime.time()
        #     init_temp =  self.temps[0].get()
        #     self.a = (this_temp-init_temp)/this_time
        #     self.b = this_temp
        #     self.timer_program.start()
        #     while self.temps[0].get() - 7


    def update_temp_sp(self):
        current_time = ttime.time()
        try:
            this_sp = self.program_sps[self.program_idx]
        except IndexError:
            this_sp = self.program_sps[-1]
        # print('time passed:', current_time - self.init_time, 'index:', self.program_idx, 'setpoint:', this_sp)
        # self.temps_sp[0].put(this_sp)
        self.program_idx += 1











if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = GUI()
    main.show()

    sys.exit(app.exec_())



