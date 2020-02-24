
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

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_info_general.ui')


class UIInfoGeneral(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE = None,
                 db = None,
                 parent = None,

                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time
        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_time)
        self.timer_update_time.start()

        self.timer_update_weather = QtCore.QTimer(self)
        self.timer_update_weather.singleShot(0, self.update_weather)
        self.timer_update_weather.setInterval(1000*60*5)
        self.timer_update_weather.timeout.connect(self.update_weather)
        self.timer_update_weather.start()
        self.db = db
        self.parent = parent
        self.RE = RE

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




