
from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request
import numpy as np

from isstools.dialogs import UpdateUserDialog
from timeit import default_timer as timer

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_general_info.ui')


class UIGeneralInfo(*uic.loadUiType(ui_path)):
    def __init__(self,
                 accelerator=None,
                 hhm = None,
                 shutters=None,
                 ic_amplifiers = None,
                 RE = None,
                 db = None,

                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_time)
        self.timer_update_time.timeout.connect(self.update_energy)
        self.timer_update_time.start()

        self.timer_update_weather = QtCore.QTimer(self)
        self.timer_update_weather.singleShot(0, self.update_weather)
        self.timer_update_weather.setInterval(1000*60*5)
        self.timer_update_weather.timeout.connect(self.update_weather)
        self.timer_update_weather.start()
        self.hhm = hhm
        self.RE = RE
        self.db = db
        self.shutters = shutters
        self.ic_amplifiers = ic_amplifiers

        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer_update_user_info = QtCore.QTimer()
            self.timer_update_user_info.timeout.connect(self.update_user_info)
            self.timer_update_user_info.start(60*1000)
            self.timer_update_user_info.singleShot(0, self.update_user_info)
            self.push_set_user_info.clicked.connect(self.set_user_info)
        else:
            self.push_update_user.setEnabled(False)


        # Initialize general settings
        self.accelerator = accelerator
        self.accelerator.beam_current.subscribe(self.update_beam_current)
        self.accelerator.status.subscribe(self.update_accelerator_status)

        self.comboBox_set_i0_gain.currentIndexChanged.connect(self.set_i0_gain)
        self.comboBox_set_it_gain.currentIndexChanged.connect(self.set_it_gain)
        self.comboBox_set_ir_gain.currentIndexChanged.connect(self.set_ir_gain)
        self.comboBox_set_if_gain.currentIndexChanged.connect(self.set_if_gain)


    def update_weather(self):
        try:
            current_weather = requests.get(
                'http://api.openweathermap.org/data/2.5/weather?zip=11973&APPID=a3be6bc4eaf889b154327fadfd9d6532').json()
            string_current_weather  = current_weather['weather'][0]['main'] + ' in Upton, NY,  it is {0:.0f} °F outside,\
                humidity is {1:.0f}%'\
                .format(((current_weather['main']['temp']-273)*1.8+32), current_weather['main']['humidity'])
            icon_url = 'http://openweathermap.org/img/w/' + current_weather['weather'][0]['icon'] + '.png'
            image = QtGui.QImage()
            image.loadFromData(urllib.request.urlopen(icon_url).read())
            self.label_current_weather_icon.setPixmap(QtGui.QPixmap(image))
        except:
            string_current_weather = 'Weather information not available'
        self.label_current_weather.setText(string_current_weather)

    def update_time(self):
        self.label_current_time.setText(
            'Today is {0}'.format(QtCore.QDateTime.currentDateTime().toString('MMMM d, yyyy, h:mm:ss ap')))

    def update_energy(self):
        energy = self.hhm.energy.read()['hhm_energy']['value']
        self.label_energy.setText('Energy is {:.1f} eV'.format(energy))
        if ((self.hhm.fb_status.get()==1) and
                (self.shutters['FE Shutter'].state.get()==0) and (self.shutters['PH Shutter'].state.get()==0)):
            self.label_feedback_status.setText('Feedback on')
            self.label_feedback_status.setStyleSheet('color: rgb(19,139,67)')
            self.label_feedback_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
        else:
            self.label_feedback_status.setText('Feedback off')
            self.label_feedback_status.setStyleSheet('color: rgb(190,190,190)')
            self.label_feedback_status_indicator.setStyleSheet('background-color: rgb(0,94,0)')

        i0_gain = self.ic_amplifiers['i0_amp'].get_gain()[0]
        it_gain = self.ic_amplifiers['it_amp'].get_gain()[0]
        ir_gain = self.ic_amplifiers['ir_amp'].get_gain()[0]
        if_gain = self.ic_amplifiers['iff_amp'].get_gain()[0]

        self.label_gain_i0.setText(f'I<sub>0</sub>: 10<sup>{i0_gain}</sup>')
        self.label_gain_it.setText(f'I<sub>t</sub>: 10<sup>{it_gain}</sup>')
        self.label_gain_ir.setText(f'I<sub>r</sub>: 10<sup>{ir_gain}</sup>')
        self.label_gain_if.setText(f'I<sub>f</sub>: 10<sup>{if_gain}</sup>')

    def update_beam_current(self, **kwargs):
        self.label_beam_current.setText('Beam current is {:.1f} mA'.format(kwargs['value']))

    def update_accelerator_status(self, **kwargs):
        if kwargs['value'] == 0:
            self.label_accelerator_status.setText('Beam available')
            self.label_accelerator_status.setStyleSheet('color: rgb(19,139,67)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
        elif kwargs['value'] == 1:
            self.label_accelerator_status.setText('Setup')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(246,229,148)')
        elif kwargs['value'] == 2:
            self.label_accelerator_status.setText('Accelerator studies')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(209,116,42)')
        elif kwargs['value'] == 3:
            self.label_accelerator_status.setText('Beam has dumped')
            self.label_accelerator_status.setStyleSheet('color: rgb(237,30,30)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(237,30,30)')
        elif kwargs['value'] == 4:
            self.label_accelerator_status.setText('Maintenance')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(200,149,251)')
        elif kwargs['value'] == 5:
            self.label_accelerator_status.setText('Shutdown')
            self.label_accelerator_status.setStyleSheet('color: rgb(190,190,190)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(190,190,190)')
        elif kwargs['value'] == 6:
            self.label_accelerator_status.setText('Unscheduled ops')
            self.label_accelerator_status.setStyleSheet('color: rgb(19,139,67)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(0,177,0)')

    def update_user_info(self):
        self.label_user_info.setText('{} is running  under Proposal {}/SAF {} '.
                                     format(self.RE.md['PI'], self.RE.md['PROPOSAL'], self.RE.md['SAF']))
        self.cycle = ['', 'Spring', 'Summer', 'Fall']
        self.label_current_cycle.setText(
            'It is {} {} NSLS Cycle'.format(self.RE.md['year'], self.cycle[int(self.RE.md['cycle'])]))

    def set_user_info(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'],
                                                self.RE.md['SAF'], self.RE.md['PI'], parent=self)
        if dlg.exec_():
            start = timer()
            self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'], self.RE.md['SAF'], self.RE.md[
                'PI'] = dlg.getValues()
            stop1 = timer()
            self.update_user_info()

    def set_i0_gain(self):
        self.ic_amplifiers['i0_amp'].set_gain(int(self.comboBox_set_i0_gain.currentText()),0)

    def set_it_gain(self):
        self.ic_amplifiers['it_amp'].set_gain(int(self.comboBox_set_it_gain.currentText()),0)

    def set_ir_gain(self):
        self.ic_amplifiers['ir_amp'].set_gain(int(self.comboBox_set_ir_gain.currentText()),0)

    def set_if_gain(self):
        self.ic_amplifiers['iff_amp'].set_gain(int(self.comboBox_set_if_gain.currentText()), 0)

