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

    sample_list_changed_signal = QtCore.pyqtSignal()

    def __init__(self,
                 RE=None,
                 parent=None,
                 sample_manager=None,
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
        self.sample_manager=sample_manager
        self.enable_fields(False)
        self.pushButton_setup_user.clicked.connect(self.setup_user)
        self.pushButton_find_proposal.clicked.connect(self.find_proposal)
        self.pushButton_select_saf.clicked.connect(self.select_saf)
        self.pushButton_cancel_setup.clicked.connect(self.cancel_setup)
        self.push_create_sample.clicked.connect(self.create_new_sample)
       # self.pushButton_cancel_setup.setEnable(False)

        self.comboBox_group.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_pi.currentIndexChanged.connect(self.select_from_comboboxes)

        self.sample_list_changed_signal.connect(self.update_sample_list)

        # Populate comboboxes
        for user in self.user_list:
            name = user['pi'][0]+' '+user['pi'][1]
            self.user_names.append(name)
            self.comboBox_pi.addItem(name)
            self.user_groups.append(user['group'])
        groups = list(set(self.user_groups))
        for group in groups:
             self.comboBox_group.addItem(group)
        # populate fields based on RE.md
        current_user =  self.RE.md['PI']
        self.lineEdit_pi_first.setText(current_user.split(' ')[0])
        self.lineEdit_pi_last.setText(current_user.split(' ')[1])
        self.spinBox_saf.setValue(int(self.RE.md['SAF']))
        self.spinBox_proposal.setValue(int(self.RE.md['proposal']))
        self.lineEdit_email.setText(self.RE.md['email'])
        self.lineEdit_group.setText(self.RE.md['institution'])


    def enable_fields(self, enable):
        elements = ['comboBox_pi',
                    'comboBox_group',
                    'pushButton_find_proposal',
                    'spinBox_proposal',
                    'spinBox_saf',
                    'listWidget_safs',
                    'listWidget_users',
                    'pushButton_select_saf']

        for element in elements:
            getattr(self, element).setEnabled(enable)
        elements = [
            'lineEdit_email',
            'lineEdit_pi_first',
            'lineEdit_pi_last',
            'lineEdit_group',
            ]
        for element in elements:
            getattr(self, element).setReadOnly(not enable)

       # self.pushButton_cancel_setup.setEnable(not enable)

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
                    self.active_user_index = -1

            else:
                self.active_user_index = self.user_names.index(new_user_name)
                self.user_list[self.active_user_index]['runs'].append(run)
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
            self.listWidget_safs.clear()
            self.listWidget_users.clear()
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
        saf = self.listWidget_safs.currentItem().text()
        self.spinBox_saf.setValue(int(saf))

    def cancel_setup(self):
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

    def create_new_sample(self):
        sample_name = self.lineEdit_sample_name.text()
        if (sample_name == '') or (sample_name.isspace()):
            message_box('Warning', 'Sample name is empty')
            return
        sample_name = remove_special_characters(sample_name)
        sample_comment = self.lineEdit_sample_comment.text()
        # positions = self._create_list_of_positions()
        self._currently_selected_index = -1
        self.sample_manager.add_new_sample(sample_name, sample_comment, [])

        new_sample = {}
        new_sample['names']=sample_name
        new_sample['comment'] = sample_comment
        new_sample['created'] = ttime.ctime()
        new_sample['timestamp'] = ttime.time()
        new_sample['archived'] = False
        if 'samples' in self.user_list[self.active_user_index].keys():
            self.user_list[self.active_user_index]['samples'].append(new_sample)
        else:
            self.user_list[self.active_user_index]['samples'] = [new_sample]


    def update_sample_list(self):
        self.listWidget_samples.clear()
        for i, sample in enumerate(self.sample_manager.samples):
            name = sample.name
            comment = sample.comment
            self.listWidget_samples.addItem(f'{name}/{comment}')
















