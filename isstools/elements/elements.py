from ophyd import (ProsilicaDetector, SingleTrigger, Component as Cpt,
                   EpicsSignal, EpicsSignalRO, ImagePlugin, StatsPlugin, ROIPlugin,
                   Device, DeviceStatus)

from PyQt4 import QtGui, QtCore

class shutter(Device):

    state = Cpt(EpicsSignal, 'Pos-Sts')
    cls = Cpt(EpicsSignal, 'Cmd:Cls-Cmd')
    opn = Cpt(EpicsSignal, 'Cmd:Opn-Cmd')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = 'red'

    def open(self):
        print('Opening {}'.format(self.name))
        self.opn.put(1)

    def close(self):
        print('Closing {}'.format(self.name))
        self.cls.put(1)

class TreeView(QtGui.QTreeView):
    def __init__(self, parent, accepted_type):
        QtGui.QTreeView.__init__(self, parent)
        self.accepted_type = accepted_type
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    def startDrag(self, dropAction):
        mime = QtCore.QMimeData()
        mime.setData('accepted_type', self.accepted_type)
        index = self.currentIndex()
        item = index.model().itemFromIndex(index)
        mime.setText(item.text())
        #mime.setData('application/x-item', '???')

        #print('Start dragging')
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.start(QtCore.Qt.CopyAction)#(QtCore.Qt.CopyAction)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("accepted_type"):
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        if (event.mimeData().data('accepted_type').data().decode("utf-8") == self.accepted_type):
            event.accept()
        else:
            event.ignore()    

    def dropEvent(self, event):
        #if self.accepted_type = event.mimeData().data('accepted_type'):
        #QtGui.QTreeView.dropEvent(self, event)
        #if event.isAccepted():
        #    print('dropEvent', hasattr(self, 'x'))
        #print('Formats: {}'.format(event.mimeData().formats()))
        #print('Mime: {}'.format(event.mimeData().data('application/x-qstandarditemmodeldatalist')))
        #data = event.mimeData().data('application/x-qabstractitemmodeldatalist')

        exists = False
        curr_item_text = event.mimeData().text()
        for i in range(self.model().rowCount()):
            if self.model().item(i).text() == curr_item_text:
                exists = True
                break

        if not exists:
            event.acceptProposedAction()
            item = QtGui.QStandardItem()
            item.setText(curr_item_text)
            parent = self.model().invisibleRootItem()
            parent.appendRow(item)
            QtGui.QTreeView.dropEvent(self, event)



