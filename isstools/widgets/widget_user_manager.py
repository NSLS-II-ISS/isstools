import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.Qt import QObject, Qt
from PyQt5.QtCore import QThread, QSettings
from PyQt5.QtWidgets import QMenu, QToolTip, QHBoxLayout, QWidget
from isstools.elements.widget_motors import UIWidgetMotors, UIWidgetMotorsWithSlider
from ..elements.elements import remove_special_characters
from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem

from isstools.elements.qmicroscope import Microscope
from isstools.dialogs import UpdateSampleInfo
from isstools.dialogs.BasicDialogs import message_box, question_message_box

import matplotlib.path as mpltPath

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_user_manager.ui')



class UIUserManager(*uic.loadUiType(ui_path)):


    def __init__(self,
                 parent=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent  = parent



        self.user_list = []
        user_groups = []
        self.enable_fields(False)
        self.pushButton_setup_user.clicked.connect(self.setup_user)
        self.comboBox_group.currentIndexChanged.connect(self.select_from_comboboxes)
        self.comboBox_pi.currentIndexChanged.connect(self.select_from_comboboxes)

        #
        self.user_list = [ {'PI':['Eli', 'Stavitski'], 'Group':'NSLS II' },
                           {'PI':['Denis', 'Leshchev'], 'Group':'NSLS II' },
                           {'PI':['Randall', 'Meyer'],'Group':'Exxon Mobil'}
                           ]
        # Populate comboboxes
        for user in self.user_list:
            name = user['PI'][0]+' '+user['PI'][1]
            self.comboBox_pi.addItem(name)
            user_groups.append(user['Group'])
        user_groups = list(set(user_groups))
        for group in user_groups:
             self.comboBox_group.addItem(group)

    def enable_fields(self, enable):
        self.lineEdit_pi_first.setEnabled(enable)
        self.lineEdit_pi_last.setEnabled(enable)
        self.lineEdit_group.setEnabled(enable)
        self.comboBox_pi.setEnabled(enable)
        self.comboBox_group.setEnabled(enable)

    def setup_user(self):
        if self.pushButton_setup_user.isChecked():
            self.enable_fields(True)
        else:
            self.enable_fields(False)



    def select_from_comboboxes(self):
        sender_object = QObject().sender()
        sender_object_name = self.sender().objectName()
        if sender_object_name ==  'comboBox_pi':
            print(10)
            self.lineEdit_pi_first.setText(sender_object.currentText())
            self.lineEdit_pi_last.setText(sender_object.currentText())
        if sender_object_name == 'comboBox_group':
            self.lineEdit_group.setText(sender_object.currentText())




