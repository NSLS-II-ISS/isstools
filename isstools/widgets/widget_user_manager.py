import re
import sys
import numpy as np
import pkg_resources
import math
import requests
import time as ttime
import uuid


from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QCursor, QStandardItem
from PyQt5.Qt import QObject, Qt
from PyQt5.QtCore import QThread, QSettings
from PyQt5.QtWidgets import QMenu, QToolTip, QHBoxLayout, QWidget, QListWidgetItem
from isstools.elements.widget_motors import UIWidgetMotors, UIWidgetMotorsWithSlider
from ..elements.elements import remove_special_characters



from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from PyQt5 import uic, QtWidgets

from xas.file_io import make_user_dir
from isscloudtools.slack import *
from isscloudtools.gmail import *
from isscloudtools.dropbox import *


from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem
from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box

from isstools.dialogs.BasicDialogs import message_box, question_message_box

import matplotlib.path as mpltPath

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_user_manager.ui')

class UIUserManager(*uic.loadUiType(ui_path)):

    sample_list_changed_signal = QtCore.pyqtSignal()

    def __init__(self,
                 RE=None,
                 parent=None,
                 sample_manager=None,
                 user_manager=None,
                 scan_manager=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.RE=RE
        self.scan_manager = scan_manager
        self.sample_manager=sample_manager
        self.user_manager=user_manager
        self.enable_fields(False)
        self.pushButton_setup_user.clicked.connect(self.setup_user)
        self.pushButton_find_proposal.clicked.connect(self.find_proposal)
        self.pushButton_select_saf.clicked.connect(self.select_saf)
        self.pushButton_cancel_setup.clicked.connect(self.cancel_setup)
        self.push_create_sample.clicked.connect(self.create_new_sample)
        self.pushButton_cancel_setup.clicked.connect(self.cancel_setup)
        self.pushButton_archive_samples.clicked.connect(self.archive_sample)
        self.pushButton_restore_samples.clicked.connect(self.restore_sample)
        self.pushButton_archive_scans.clicked.connect(self.archive_scan)
        self.pushButton_restore_scans.clicked.connect(self.restore_scan)

        self.pushButton_add_metadata_key.clicked.connect(self.add_metadata_key)
        self.pushButton_remove_metadata_key.clicked.connect(self.remove_metadata_key)

       # self.pushButton_cancel_setup.setEnable(False)



        self.sample_list_changed_signal.connect(self.update_sample_list)
        self.comboBox_affiliations.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.activated.connect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.connect(self.select_from_comboboxes)

        self.checkBox_show_archived_samples.toggled.connect(self.show_archives)
        self.checkBox_show_archived_scans.toggled.connect(self.show_archives)

        self.populate_comboboxes()
        self.initialize()

        self.listWidget_samples_archived.hide()
        self.listWidget_scans_archived.hide()
        self.pushButton_restore_scans.hide()
        self.pushButton_restore_samples.hide()

    def initialize(self):
        _, _current_user =  self.user_manager.current_user()
        self.lineEdit_user_first.setText(_current_user['first_name'])
        self.lineEdit_user_last.setText(_current_user['last_name'])
        self.spinBox_saf.setValue(int(_current_user['runs'][-1]['saf']))
        self.spinBox_proposal.setValue(int(_current_user['runs'][-1]['proposal']))
        self.lineEdit_email.setText(_current_user['email'])
        self.lineEdit_affiliation.setText(_current_user['affiliation'])
        for _key in _current_user['metadata']:
            self.listWidget_metadata.addItem(_key)
        self.update_sample_list()
        self.update_scan_list()


    def add_metadata_key(self):
        _key = self.lineEdit_new_metadata_key.text()
        if _key !='':
            self.user_manager.add_metadata_key(_key)
            self.listWidget_metadata.addItems(_key)

    def remove_metadata_key(self):
        _key = self.lineEdit_new_metadata_key.text()
        if _key !='':
            pass

    def archive_sample(self):
        for item in self.listWidget_samples.selectedItems():
            indx = self.sample_manager.uid_to_sample_index(item.toolTip())
            self.sample_manager.archive_at_index(indx)

    def restore_sample(self):
        for item in self.listWidget_samples_archived.selectedItems():
            indx = self.sample_manager.uid_to_sample_index(item.toolTip())
            self.sample_manager.restore_at_index(indx)

    def update_scan_list(self):
        self.listWidget_scans.clear()
        self.listWidget_scans_archived.clear()
        for scan in self.scan_manager.scan_list_local:
            item = QListWidgetItem(scan['scan_def'])
            item.setToolTip(scan['uid'])
            if scan['archived']:
                self.listWidget_scans_archived.addItem(item)
            else:
                self.listWidget_scans.addItem(item)
    def restore_scan(self):
        for item in self.listWidget_scans_archived.selectedItems():
            self.scan_manager.restore_scan_at_uid(item.toolTip())
        self.parent.widget_scan_manager.update_local_manager_list()

    def archive_scan(self):
        for item in self.listWidget_scans.selectedItems():
            self.scan_manager.archive_scan_at_uid(item.toolTip())
        self.parent.widget_scan_manager.update_local_manager_list()

    def update_sample_list(self):
        self.listWidget_samples.clear()
        self.listWidget_samples_archived.clear()
        for sample in self.sample_manager.samples:
            item = QListWidgetItem(f'{sample.name} - {sample.comment}')
            item.setToolTip(sample.uid)
            if sample.archived:
                self.listWidget_samples_archived.addItem(item)
            else:
                self.listWidget_samples.addItem(item)



    def populate_comboboxes(self):
        self.comboBox_affiliations.currentIndexChanged.disconnect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.disconnect(self.select_from_comboboxes)
        self.comboBox_users.activated.disconnect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.disconnect(self.select_from_comboboxes)
        self.comboBox_users.clear()
        self.comboBox_affiliations.clear()
        affiliations=[]
        for user in self.user_manager.users:
            self.comboBox_users.addItem(f"{user['first_name']} {user['last_name']}")
            affiliations.append(user['affiliation'])
        affiliations = list(set(affiliations))
        for affiliation in affiliations:
            self.comboBox_affiliations.addItem(affiliation)
        self.comboBox_affiliations.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_users.activated.connect(self.select_from_comboboxes)
        self.comboBox_affiliations.activated.connect(self.select_from_comboboxes)

    def show_archives(self):
        sender_object = QObject().sender()
        object_dict = {self.checkBox_show_archived_samples: [self.listWidget_samples_archived, self.pushButton_restore_samples],
                       self.checkBox_show_archived_scans: [self.listWidget_scans_archived, self.pushButton_restore_scans]}
        if sender_object.isChecked():
            for object in object_dict[sender_object]:
                object.show()
        else:
            for object in object_dict[sender_object]:
                object.hide()

    def enable_fields(self, enable):
        elements = ['comboBox_users',
                    'comboBox_affiliations',
                    'pushButton_find_proposal',
                    'spinBox_proposal',
                    'spinBox_saf',
                    'listWidget_safs',
                    'listWidget_experimenters',
                    'pushButton_select_saf']

        for element in elements:
            getattr(self, element).setEnabled(enable)
        elements = [
            'lineEdit_email',
            'lineEdit_user_first',
            'lineEdit_user_last',
            'lineEdit_affiliation',
            ]
        for element in elements:
            getattr(self, element).setReadOnly(not enable)

       # self.pushButton_cancel_setup.setEnable(not enable)

    def setup_user(self):
        if self.pushButton_setup_user.isChecked():
            self.current_first = self.lineEdit_user_first.text()
            self.current_last = self.lineEdit_user_last.text()
            self.current_affiliation = self.lineEdit_affiliation.text()
            self.current_email = self.lineEdit_email.text()
            self.enable_fields(True)
        else:
            self.enable_fields(False)
            _first = self.lineEdit_user_first.text()
            _last = self.lineEdit_user_last.text()
            _affiliation = self.lineEdit_affiliation.text()
            _email = self.lineEdit_email.text()

            self.RE.md['PI'] = f'{_first} {_last}'
            self.RE.md['affiliation'] = _affiliation
            self.RE.md['email'] = _email

            self.user_manager.set_user(_first, _last,_affiliation,_email)
            _proposal = self.spinBox_proposal.value()
            _saf = self.spinBox_saf.value()
            _experimenters = []
            for j in range(self.listWidget_experimenters.count()):
                _experimenters.append(self.listWidget_experimenters.item(j).text())
            self.user_manager.add_run(_proposal, _saf, _experimenters)
            self.cloud_setup(email_address=_email)
            self.populate_comboboxes()



    def select_from_comboboxes(self):
        sender_object = QObject().sender()
        sender_object_name = self.sender().objectName()
        if sender_object_name == 'comboBox_users':
            self.lineEdit_user_first.setText(sender_object.currentText().split(' ')[0])
            self.lineEdit_user_last.setText(sender_object.currentText().split(' ')[1])
        if sender_object_name == 'comboBox_affiliations':
            self.lineEdit_affiliation.setText(sender_object.currentText())

    def find_proposal(self):
        headers = {'accept': 'application/json',}
        proposal = str(self.spinBox_proposal.value())
        proposal_info = requests.get(f'https://api-staging.nsls2.bnl.gov/proposal/{proposal}', headers=headers).json()
        if 'error_message' in proposal_info.keys():
            error_message_box('Proposal not found')
        else:
            self.listWidget_safs.clear()
            self.listWidget_experimenters.clear()
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
                self.listWidget_experimenters.addItem(item)


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

        self.sample_manager._currently_selected_index = -1
        self.sample_manager.add_new_sample(sample_name, sample_comment, [])

    def cancel_setup(self):
        self.pushButton_setup_user.setChecked(False)
        self.lineEdit_user_first.setText(self.current_first)
        self.lineEdit_user_last.setText(self.current_last)
        self.lineEdit_affiliation.setText(self.current_affiliation)
        self.lineEdit_email.setText(self.current_email)
        self.enable_fields(False)



















