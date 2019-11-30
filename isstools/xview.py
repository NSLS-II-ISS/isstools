import sys
import pkg_resources
from PyQt5 import  QtWidgets, uic
from isstools.xasproject import xasproject

from isstools.widgets import widget_xview_data, widget_xview_project

if sys.platform == 'darwin':
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview-mac.ui')
else:
    ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xview.ui')

class XviewGui(*uic.loadUiType(ui_path)):
    def __init__(self, db=None,*args, **kwargs):
        self.db = db
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.xasproject = xasproject.XASProject()

        self.widget_data = widget_xview_data.UIXviewData(db=db, parent=self)
        self.layout_data.addWidget(self.widget_data)

        self.widget_project = widget_xview_project.UIXviewProject(parent=self)
        self.layout_project.addWidget(self.widget_project)

    def  set_figure(self, axis, canvas, label_x='', label_y=''):
        axis.legend(fontsize='small')
        axis.grid(alpha=0.4)
        axis.set_ylabel(label_y, size='13')
        axis.set_xlabel(label_x, size='13')
        canvas.draw_idle()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main = XviewGui()
    main.show()

    sys.exit(app.exec_())
