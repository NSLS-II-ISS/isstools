
from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request
import numpy as np
import os
import re
import time as ttime

from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from timeit import default_timer as timer
from isstools.dialogs.BasicDialogs import message_box
import bluesky.plan_stubs as bps

from issgoogletools.initialize import get_dropbox_service, get_gmail_service
from issgoogletools.gmail import create_html_message, upload_draft, send_draft
import uuid

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_info_beamline.ui')




class UIInfoBeamline(*uic.loadUiType(ui_path)):

    def __init__(self,
                 accelerator=None,
                 hhm = None,
                 shutters=None,
                 ic_amplifiers = None,
                 apb = None,
                 RE = None,
                 db = None,
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_status)
        self.timer_update_time.start()

        self.hhm = hhm
        self.RE = RE
        self.db = db
        self.shutters = shutters
        self.ic_amplifiers = ic_amplifiers
        self.parent = parent
        self.apb = apb
        self.hhm= hhm

        # Initialize general settings
        self.accelerator = accelerator
        self.accelerator.beam_current.subscribe(self.update_beam_current)
        self.accelerator.status.subscribe(self.update_accelerator_status)

        self.comboBox_set_i0_gain.currentIndexChanged.connect(self.set_i0_gain)
        self.comboBox_set_it_gain.currentIndexChanged.connect(self.set_it_gain)
        self.comboBox_set_ir_gain.currentIndexChanged.connect(self.set_ir_gain)
        self.comboBox_set_if_gain.currentIndexChanged.connect(self.set_if_gain)
        self.push_get_offsets.clicked.connect(parent.widget_beamline_setup.get_offsets)
        self.push_set_energy.clicked.connect(self.set_energy)
        self.push_jog_pitch_neg.clicked.connect(self.tweak_pitch_neg)
        self.push_jog_pitch_pos.clicked.connect(self.tweak_pitch_pos)



        daq_rate = self.apb.acq_rate.get()
        self.spinBox_daq_rate.setValue(daq_rate)
        self.spinBox_daq_rate.valueChanged.connect(self.update_daq_rate)

        enc_rate_in_points = hhm.enc.filter_dt.get()
        enc_rate = 1/(89600*10*1e-9)/1e3
        self.spinBox_enc_rate.setValue(enc_rate)
        self.spinBox_enc_rate.valueChanged.connect(self.update_enc_rate)





    def update_status(self):

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
        if (self.RE.state == 'idle'):
            self.label_RE.setText('Run Engine is idle')
            self.label_RE_status_indicator.setStyleSheet('background-color: rgb(0,94,0)')
        elif (self.RE.state == 'running'):
            self.label_RE.setText('Run Engine is running')
            self.label_RE_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
        elif (self.RE.state == 'paused'):
            self.label_RE.setText('Run Engine is paused')
            self.label_RE_status_indicator.setStyleSheet('background-color: rgb(255,153,51)')
        elif (self.RE.state == 'abort'):
            self.label_RE.setText('Run Engine is aborted')
            self.label_RE_status_indicator.setStyleSheet('background-color: rgb(255,0,0)')


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


    def set_i0_gain(self):
        self.ic_amplifiers['i0_amp'].set_gain(int(self.comboBox_set_i0_gain.currentText()),0)

    def set_it_gain(self):
        self.ic_amplifiers['it_amp'].set_gain(int(self.comboBox_set_it_gain.currentText()),0)

    def set_ir_gain(self):
        self.ic_amplifiers['ir_amp'].set_gain(int(self.comboBox_set_ir_gain.currentText()),0)

    def set_if_gain(self):
        self.ic_amplifiers['iff_amp'].set_gain(int(self.comboBox_set_if_gain.currentText()), 0)

    def set_energy(self):
        energy = self.hhm.energy.read()['hhm_energy']['value']
        dlg = SetEnergy.SetEnergy(round(energy), parent=self)
        if dlg.exec_():
            try:
                new_energy=float(dlg.getValues())
                print(new_energy)
                if (new_energy > 4700) and (new_energy < 32000):
                    self.RE(bps.mv(self.hhm.energy, new_energy))
                else:
                    raise ValueError
            except Exception as exc:
                message_box('Incorrect energy','Energy should be within 4700-32000 eV range')

    def tweak_pitch_pos(self):
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(False)
        pitch = self.hhm.pitch.read()['hhm_pitch']['value']
        self.RE(bps.mv(self.hhm.pitch, pitch+0.025))

    def tweak_pitch_neg(self):
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(False)
        pitch = self.hhm.pitch.read()['hhm_pitch']['value']
        self.RE(bps.mv(self.hhm.pitch, pitch-0.025))

    def update_daq_rate(self):
        daq_rate = self.spinBox_daq_rate.value()
        # 374.94 is the nominal RF frequency
        divider = int(374.94/daq_rate)
        self.RE(bps.abs_set(self.apb.divide, divider, wait=True))

    def update_enc_rate(self):
        enc_rate = self.spinBox_enc_rate.value()
        rate_in_points = (1/(enc_rate*1e3))*1e9/10

        rate_in_points_rounded = int(np.ceil(rate_in_points / 100.0) * 100)
        self.RE(bps.abs_set(self.hhm.enc.filter_dt, rate_in_points_rounded, wait=True))

        #self.RE(bps.abs_set(self.hhm.enc.filter_dt, rate_in_points, wait=True))





