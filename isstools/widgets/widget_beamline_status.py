from PyQt5 import uic, QtCore, QtWidgets
import pkg_resources


from isstools.dialogs import UpdateUserDialog


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_status.ui')


class UIBeamlineStatus(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()

    def __init__(self,
                 shutters={},
                 hhm=None,
                 det_dict={},
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Initialize Ophyd elements
        self.shutters_sig.connect(self.change_shutter_color)
        self.shutters = shutters
        if hhm is not None:
            self.hhm = hhm
            self.hhm.energy.subscribe(self.update_current_energy)
        if det_dict !={}:
            self.i0 = det_dict['pba1_adc7']['obj']
            self.it = det_dict['pba1_adc7']['obj']
            self.ir = det_dict['pba1_adc1']['obj']
            self.iff = det_dict['pba2_adc6']['obj']
            self.i0.volt.subscribe(self.update_detector_currents)


        self.shutters_buttons = []
        for key, item in zip(self.shutters.keys(), self.shutters.items()):
            self.shutter_layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(key)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.shutter_layout.addWidget(label)
            label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

            button = QtWidgets.QPushButton('')
            button.setFixedSize(self.height() * 0.5, self.height() * 0.5)
            self.shutter_layout.addWidget(button)
            # button.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

            self.horizontalLayout_shutters.addLayout(self.shutter_layout)

            self.shutters_buttons.append(button)
            button.setFixedWidth(button.height() * 1.2)
            QtCore.QCoreApplication.processEvents()

            if hasattr(item[1].state, 'subscribe'):
                item[1].button = button
                item[1].state.subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if int(shutter.state.value):
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                button.clicked.connect(toggle_shutter_call(item[1]))

                if item[1].state.value == 0:
                    button.setStyleSheet("background-color: lime")
                else:
                    button.setStyleSheet("background-color: red")

            elif hasattr(item[1], 'subscribe'):
                item[1].output.parent.button = button
                item[1].subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if shutter.state == 'closed':
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                if item[1].state == 'closed':
                    button.setStyleSheet("background-color: red")
                elif item[1].state == 'open':
                    button.setStyleSheet("background-color: lime")

                button.clicked.connect(toggle_shutter_call(item[1]))

        if self.horizontalLayout_shutters.count() <= 1:
            self.groupBox_shutters.setVisible(False)

        self.pitch_old=self.hhm.pitch.get().user_readback
        self.timer_update_feedback_status = QtCore.QTimer(self)
        self.timer_update_feedback_status.setInterval(500)
        self.timer_update_feedback_status.timeout.connect(self.update_feedback_status)
        self.timer_update_feedback_status.start()

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if 'obj' in kwargs.keys():
            if hasattr(kwargs['obj'].parent, 'button'):
                self.current_button = kwargs['obj'].parent.button

                if int(value) == 0:
                    self.current_button_color = 'lime'
                elif int(value) == 1:
                    self.current_button_color = 'red'

                self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)

    def update_current_energy(self, **kwargs):
        self.label_current_energy.setText('{:.1f} eV'.format(kwargs['value']))

    def update_feedback_status(self,**kwargs):
        pitch_new = self.hhm.pitch.get().user_readback
        if (self.hhm.fb_status.value == 1) and (pitch_new != self.pitch_old):
            self.pitch_old = pitch_new
            self.label_hhm_feedback_indicator.setStyleSheet('background-color: rgb(95,249,95)')
        else:
            self.label_hhm_feedback_indicator.setStyleSheet('background-color: rgb(95,144,95)')

    def update_detector_currents(self, *args, **kwargs):


        ival = self.i0.volt.value
        element = self.label_i0_current
        element.setText('{:.3f} V'.format(ival))
        if ival > -3.5:
            element.setStyleSheet('color: rgb(0,0,0)')
        elif ival< -3.5 and ival> -3.9:
            element.setStyleSheet('color: rgb(209,116,42)')
        else:
            element.setStyleSheet('color: rgb(209,116,42)')

        ival = self.it.volt.value
        element = self.label_it_current
        element.setText('{:.3f} V'.format(ival))
        if ival > -3.5:
            element.setStyleSheet('color: rgb(0,0,0)')
        elif ival< -3.5 and ival> -3.9:
            element.setStyleSheet('color: rgb(209,116,42)')
        else:
            element.setStyleSheet('color: rgb(209,116,42)')

        ival = self.ir.volt.value
        element = self.label_ir_current
        element.setText('{:.3f} V'.format(ival))
        if ival > -3.5:
            element.setStyleSheet('color: rgb(0,0,0)')
        elif ival< -3.5 and ival> -3.9:
            element.setStyleSheet('color: rgb(209,116,42)')
        else:
            element.setStyleSheet('color: rgb(209,116,42)')


        ival = self.iff.volt.value
        element = self.label_if_current
        element.setText('{:.3f} V'.format(ival))
        if ival > -3.5:
            element.setStyleSheet('color: rgb(0,0,0)')
        elif ival< -3.5 and ival> -3.9:
            element.setStyleSheet('color: rgb(209,116,42)')
        else:
            element.setStyleSheet('color: rgb(209,116,42)')


