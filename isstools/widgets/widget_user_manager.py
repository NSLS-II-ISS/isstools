import re
import sys
import numpy as np
import pkg_resources
import math
import requests
import time as ttime
import uuid


from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.Qt import QObject, Qt
from PyQt5.QtCore import QThread, QSettings
from PyQt5.QtWidgets import QMenu, QToolTip, QHBoxLayout, QWidget, QListWidgetItem
from isstools.elements.widget_motors import UIWidgetMotors, UIWidgetMotorsWithSlider
from ..elements.elements import remove_special_characters



from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from timeit import default_timer as timer
from isstools.dialogs.BasicDialogs import message_box,question_message_box
from isscloudtools.initialize import get_slack_service, get_dropbox_service, get_gmail_service
import bluesky.plan_stubs as bps
from PyQt5 import uic, QtWidgets

from xas.file_io import make_user_dir
from isscloudtools.slack import *
from isscloudtools.gmail import *
from isscloudtools.dropbox import *


from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem
from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box

from isstools.elements.qmicroscope import Microscope
from isstools.dialogs import UpdateSampleInfo
from isstools.dialogs.BasicDialogs import message_box, question_message_box

import matplotlib.path as mpltPath

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_user_manager.ui')

class UIUserManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 RE=None,
                 parent=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent  = parent
        self.user_list = [ {'pi':['Eli', 'Stavitski'], 'group':'NSLS II'},
                           {'pi':['Denis', 'Leshchev'], 'group':'NSLS II'},
                           {'pi':['Randall', 'Meyer'],'group':'Exxon Mobil'}
                           ]
        self.RE=RE
        self.user_groups = []
        self.user_names = []
        self.enable_fields(False)
        self.pushButton_setup_user.clicked.connect(self.setup_user)
        self.pushButton_find_proposal.clicked.connect(self.find_proposal)
        self.pushButton_select_saf.clicked.connect(self.select_saf)

        self.comboBox_group.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_pi.currentIndexChanged.connect(self.select_from_comboboxes)

        #

        # Populate comboboxes
        for user in self.user_list:
            name = user['pi'][0]+' '+user['pi'][1]
            self.user_names.append(name)
            self.comboBox_pi.addItem(name)
            self.user_groups.append(user['group'])
        groups = list(set(self.user_groups))
        for group in groups:
             self.comboBox_group.addItem(group)

    def enable_fields(self, enable):
        elements = ['lineEdit_pi_first',
                    'lineEdit_pi_last',
                    'lineEdit_group',
                    'comboBox_pi',
                    'lineEdit_email',
                    'comboBox_group',
                    'pushButton_find_proposal',
                    'spinBox_proposal',
                    'spinBox_saf',
                    'listWidget_safs',
                    'listWidget_users',
                    'pushButton_select_saf']

        for element in elements:
            getattr(self, element).setEnabled(enable)

    def setup_user(self):
        if self.pushButton_setup_user.isChecked():
            self.enable_fields(True)
        else:
            self.enable_fields(False)
            new_user_name = f'{self.lineEdit_pi_first.text()} {self.lineEdit_pi_last.text()}'
            run = {}
            run['uid'] = str(uuid.uuid4())[: 8]
            run['start'] = ttime.ctime()
            run['timestamp'] = ttime.time()
            run['proposal'] = self.spinBox_proposal.value()
            run['saf'] = self.spinBox_saf.value()
            if new_user_name not in self.user_names:
                ret = question_message_box(self, 'New user', 'Create a new user?')
                if ret:
                    runs = []
                    new_PI = {}
                    new_PI['pi']=[self.lineEdit_pi_first.text(), self.lineEdit_pi_last.text()]
                    new_PI['uid'] = str(uuid.uuid4())[: 8]
                    new_PI['group'] = self.lineEdit_group.text()
                    runs.append(run)
                    new_PI['runs'] = runs
                    self.user_list.append(new_PI)
                    self.user_names.append(new_user_name)
                    new_PI['email'] = self.lineEdit_email.text()
            else:
                index = self.user_names.index(new_user_name)
                self.user_list[index]['runs'].append(run)
            self.cloud_setup(email_address=self.lineEdit_email.text())

    def select_from_comboboxes(self):
        sender_object = QObject().sender()
        sender_object_name = self.sender().objectName()
        if sender_object_name ==  'comboBox_pi':
            print(10)
            self.lineEdit_pi_first.setText(sender_object.currentText().split(' ')[0])
            self.lineEdit_pi_last.setText(sender_object.currentText().split(' ')[1])
        if sender_object_name == 'comboBox_group':
            self.lineEdit_group.setText(sender_object.currentText())

    def find_proposal(self):
        headers = {'accept': 'application/json',}
        proposal = str(self.spinBox_proposal.value())
        proposal_info = requests.get(f'https://api-staging.nsls2.bnl.gov/proposal/{proposal}', headers=headers).json()
        if 'error_message' in proposal_info.keys():
            error_message_box('Proposal not found')
        else:
            safs = proposal_info['safs']
            for saf in safs:
                item = QListWidgetItem(saf['saf_id'])
                if saf['status'] != 'APPROVED':
                    item.setForeground(Qt.red)
                self.listWidget_safs.addItem(item)
            users = proposal_info['users']
            for user in users:
                item = QListWidgetItem(user['first_name']+ ' ' +user['last_name'])
                if user['is_pi']:
                    item.setForeground(Qt.blue)
                self.listWidget_users.addItem(item)


    def select_saf(self):
        pass

    def cloud_setup(self, email_address = None):
        year = self.RE.md['year']
        cycle = self.RE.md['cycle']
        proposal = self.RE.md['proposal']
        PI = self.RE.md['PI']
        slack_channel = f'{year}-{cycle}-{proposal}'
        channel_id,channel_info = slack_channel_exists(self.parent.slack_client_bot,slack_channel)
        print(channel_id)
        if not channel_id:
            print('Slack channel not found, Creating new channel...')
            channel_id, channel_info = slack_create_channel(self.parent.slack_client_bot, slack_channel)
            slack_invite_to_channel(self.parent.slack_client_bot,channel_id)


        slack_url =  f'https://app.slack.com/client/T0178K9UAE6/{channel_id}'
        self.RE.md['slack_channel'] = channel_id

        dropbox_folder =f'/{year}/{cycle}/{proposal}'
        if not dropbox_folder_exists(self.parent.dropbox_service,dropbox_folder):
            dropbox_create_folder(self.parent.dropbox_service, dropbox_folder)

        dropbox_url = dropbox_get_shared_link(self.parent.dropbox_service, dropbox_folder)

        if email_address ==None:
            dlg = GetEmailAddress.GetEmailAddress('', parent=self)
            if dlg.exec_():
                email_address = dlg.getValue()

        regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
        if re.search(regex, email_address):
            # print(f'email {email_address}')
            pass
        else:
            message_box('Error', 'Invaild email')
            return 0


        message = create_html_message(
            'staff08id@gmail.com',
            email_address,
            f'ISS beamline results Proposal {proposal}',
            f'<p> Dear {PI},</p> '
            f'<p>Slack channel to monitor yor experiemnt is {slack_url} </p>'
            f'<p>Data files will be uploaded to Dropbox folder at {dropbox_url} </p>'
            f'<p> Sincerely, </p> '
            f'<p> ISS Staff </p>'
            )

        draft = upload_draft(self.parent.gmail_service, message)
        sent = send_draft(self.parent.gmail_service, draft)
        print('Email sent')














