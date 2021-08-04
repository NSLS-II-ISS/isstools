import json
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from isstools.elements.elements import elements_lines_dict

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_registry.ui')
from xraydb import xray_line
import bluesky.plan_stubs as bps


class UISampleRegistry(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None, settings=None, RE=None, sample_registry=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.settings = settings
        self.RE = RE
        self.sample_registry = sample_registry

        self.pushButton_sreg_get_start.clicked.connect(self.set_start_sreg_points)
        self.pushButton_sreg_get_end.clicked.connect(self.set_end_sreg_points)
        self.pushButton_sreg_initialize.clicked.connect(self.sreg_initialize)
        self.pushButton_sreg_reset.clicked.connect(self.sreg_reset)
        self.pushButton_sreg_save.clicked.connect(self.sreg_save_to_file)
        self.pushButton_sreg_load.clicked.connect(self.sreg_load_file)
        self.pushButton_sreg_move_to_beg.clicked.connect(self.sreg_move_to_beginning)
        self.pushButton_sreg_move_to_end.clicked.connect(self.sreg_move_to_end)
        self.pushButton_sreg_move_to_next.clicked.connect(self.sreg_move_to_next)
        self.pushButton_sreg_move_to_unexposed.clicked.connect(self.sreg_move_to_unexposed)
        self.pushButton_sreg_set_current_as_exposed.clicked.connect(self.sreg_set_current_as_exposed)
        self.pushButton_sreg_select_file.clicked.connect(self.sreg_select_load_file)


        self.pushButton_detach.clicked.connect(self.detach)

        self.lineEdit_sreg_file.setText(self.settings.value('sample_registry_filename', defaultValue=''))

    def detach(self):
        self.detached_ui = UISampleRegistry(self.parent, self.settings, self.RE, self.sample_registry)
        self.detached_ui.show()
        self.detached_ui.pushButton_detach.setEnabled(False)


    def get_current_stage_values(self):
        x = self.sample_registry.sample_x.user_readback.get()
        y = self.sample_registry.sample_y.user_readback.get()
        z = self.sample_registry.sample_z.user_readback.get()
        return x, y, z

    def set_start_sreg_points(self):
        x, y, z = self.get_current_stage_values()
        self.spinBox_sreg_x_start.setValue(x)
        self.spinBox_sreg_y_start.setValue(y)
        self.spinBox_sreg_z_start.setValue(z)

    def set_end_sreg_points(self):
        x, y, z = self.get_current_stage_values()
        self.spinBox_sreg_x_end.setValue(x)
        self.spinBox_sreg_y_end.setValue(y)
        self.spinBox_sreg_z_end.setValue(z)

    def sreg_initialize(self):
        x1 = self.spinBox_sreg_x_start.value()
        y1 = self.spinBox_sreg_y_start.value()
        z1 = self.spinBox_sreg_z_start.value()

        x2 = self.spinBox_sreg_x_end.value()
        y2 = self.spinBox_sreg_y_end.value()
        z2 = self.spinBox_sreg_z_end.value()

        step = self.spinBox_sreg_step.value()

        self.sample_registry.initialize(x1, y1, z1, x2, y2, z2, step=step)
        self.label_point_counter.setText(str())

    def _gen_label_text(self, cur_idx):
        if type(cur_idx) == str:
            return f'{cur_idx} / {self.label_point_counter.npoints}'


    def sreg_reset(self):
        self.sample_registry.reset()

    def sreg_save_to_file(self):
        user_folder_path = (self.sample_registry.root_path +
                            f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['PROPOSAL']}")
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save sample registry...', user_folder_path, '*.json',
                                              options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        if not filename.endswith('.json'):
            filename += '.json'

        self.lineEdit_sreg_file.setText(filename)
        self.sample_registry.save(filename)
        self.sample_registry.set_dump_file(filename)
        self.settings.setValue('sample_registry_filename', filename)


    def sreg_select_load_file(self):
        user_folder_path = (self.sample_registry.root_path +
                           f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['PROPOSAL']}")
        filename = QtWidgets.QFileDialog.getOpenFileName(directory=user_folder_path,
                                                         filter='*.json', parent=self)[0]
        self.lineEdit_sreg_file.setText(filename)

    # def sreg_load_file(self):
    #     user_folder_path = (self.sample_registry.root_path +
    #                         f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['PROPOSAL']}")
    #     filename = QtWidgets.QFileDialog.getOpenFileName(directory=user_folder_path,
    #                                                      filter='*.json', parent=self)[0]
    #     self.lineEdit_sreg_file.setText(filename)
    #     self._sreg_load_file()

    def sreg_load_file(self):
        filename = self.lineEdit_sreg_file.text()
        self.sample_registry.load(filename)
        self.sample_registry.set_dump_file(filename)
        self.settings.setValue('sample_registry_filename', filename)


    def sreg_move_to_beginning(self):
        plan = self.sample_registry.goto_start_plan()
        self.RE(plan)

    def sreg_move_to_end(self):
        plan = self.sample_registry.goto_end_plan()
        self.RE(plan)

    def sreg_move_to_next(self):
        plan = self.sample_registry.goto_next_point_plan()
        self.RE(plan)

    def sreg_move_to_unexposed(self):
        plan = self.sample_registry.goto_unexposed_point_plan()
        self.RE(plan)

    def sreg_set_current_as_exposed(self):
        self.sample_registry.set_current_point_exposed()







