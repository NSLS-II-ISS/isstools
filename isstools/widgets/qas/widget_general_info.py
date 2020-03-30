from PyQt5 import uic, QtGui, QtCore
import pkg_resources

import isstools.widgets.widget_general_info as widget_general_info

ui_path = pkg_resources.resource_filename("isstools", "ui/ui_general_info_qas.ui")


class UIGeneralInfo(*uic.loadUiType(ui_path), widget_general_info.UIGeneralInfo):
    def __init__(
        self, *args, **kwargs,
    ):

        super().__init__(*args, **kwargs)
