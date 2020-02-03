
from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request
import numpy as np
import os
import re

from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from timeit import default_timer as timer
from isstools.dialogs.BasicDialogs import message_box
import bluesky.plan_stubs as bps

from issgoogletools.initialize import get_dropbox_service, get_gmail_service
from issgoogletools.gmail import create_html_message, upload_draft, send_draft
import uuid

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_general_info.ui')




class UIGeneralInfo(*uic.loadUiType(ui_path)):
    def __init__(self,
                 accelerator=None,
                 hhm = None,
                 shutters=None,
                 ic_amplifiers = None,
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

        # self.timer_update_weather = QtCore.QTimer(self)
        # self.timer_update_weather.singleShot(0, self.update_weather)
        # self.timer_update_weather.setInterval(1000*60*5)
        # self.timer_update_weather.timeout.connect(self.update_weather)
        # self.timer_update_weather.start()
        self.hhm = hhm
        self.RE = RE
        self.db = db
        self.shutters = shutters
        self.ic_amplifiers = ic_amplifiers
        self.parent = parent

        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer_update_user_info = QtCore.QTimer()
            self.timer_update_user_info.timeout.connect(self.update_user_info)
            self.timer_update_user_info.start(60*1000)
            self.timer_update_user_info.singleShot(0, self.update_user_info)
            self.push_set_user_info.clicked.connect(self.set_user_info)
            self.push_send_results.clicked.connect(self.send_results)

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
        self.push_get_offsets.clicked.connect(parent.widget_beamline_setup.get_offsets)
        self.push_set_energy.clicked.connect(self.set_energy)
        self.push_jog_pitch_neg.clicked.connect(self.tweak_pitch_neg)
        self.push_jog_pitch_pos.clicked.connect(self.tweak_pitch_pos)

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


    def update_status(self):
        self.label_current_time.setText(
            'Today is {0}'.format(QtCore.QDateTime.currentDateTime().toString('MMMM d, yyyy, h:mm:ss ap')))
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




    def send_results(self):

        dlg = GetEmailAddress.GetEmailAddress('', parent=self)
        if dlg.exec_():
            email_address = dlg.getValue()
            regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
            if re.search(regex, email_address):
                 #print(f'email {email_address}')
                pass
            else:
                message_box('Error', 'Invaild email')
                return 0


        year=self.RE.md['year']
        cycle=self.RE.md['cycle']
        proposal = self.RE.md['PROPOSAL']
        PI = self.RE.md['PI']
        working_directory = f'/nsls2/xf08id/users/{year}/{cycle}/{proposal}'
        zip_file = f'{working_directory}/{proposal}.zip'

        id = str(uuid.uuid4())[0:5]

        zip_id_file = f'{proposal}-{id}.zip'

        if os.path.exists(zip_file):
            os.remove(zip_file)

        os.system(f'zip {zip_file} {working_directory}/*.dat ')
        dropbox_service =  get_dropbox_service()
        with open(zip_file,"rb") as f:
            file_id = dropbox_service.files_upload(f.read(),f'/{year}/{cycle}/{zip_id_file}')


        file_link = dropbox_service.sharing_create_shared_link(f'/{year}/{cycle}/{zip_id_file}')
        link_url =  file_link.url
        print('Upload succesful')

        gmail_service = get_gmail_service()
        message = create_html_message(
            'staff08id@gmail.com',
            email_address,
            f'ISS beamline results Proposal {proposal}',
            f' <p> Dear {PI},</p> <p>You can download the result of your experiment at ISS under proposal {proposal} here,</p> <p> {link_url} </p> <p> Sincerely, </p> <p> ISS Staff </p>'
            )

        draft = upload_draft(gmail_service, message)
        sent = send_draft(gmail_service, draft)
        print('Email sent')




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