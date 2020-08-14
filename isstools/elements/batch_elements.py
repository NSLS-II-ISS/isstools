import numpy as np
import pkg_resources
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.Qt import QObject
import copy

path_icon_experiment = pkg_resources.resource_filename('isstools', 'icons/experiment.png')
icon_experiment = QtGui.QIcon()
icon_experiment.addPixmap(QtGui.QPixmap(path_icon_experiment), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_sample = pkg_resources.resource_filename('isstools', 'icons/sample.png')
icon_sample = QtGui.QIcon()
icon_sample.addPixmap(QtGui.QPixmap(path_icon_sample), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_scan = pkg_resources.resource_filename('isstools', 'icons/scan.png')
icon_scan = QtGui.QIcon()
icon_scan.addPixmap(QtGui.QPixmap(path_icon_scan), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_service = pkg_resources.resource_filename('isstools', 'icons/service.png')
icon_service = QtGui.QIcon()
icon_service.addPixmap(QtGui.QPixmap(path_icon_service), QtGui.QIcon.Normal, QtGui.QIcon.Off)


def _create_batch_experiment(model, experiment_name, experiment_rep):
    parent = model.invisibleRootItem()
    batch_experiment = 'Batch experiment "{}" repeat {} times' \
        .format(experiment_name, experiment_rep)
    new_item = QtGui.QStandardItem(batch_experiment)
    new_item.name = batch_experiment
    new_item.setEditable(False)
    new_item.setDropEnabled(True)
    new_item.item_type = 'experiment'
    new_item.repeat = experiment_rep
    new_item.setIcon(icon_experiment)
    parent.appendRow(new_item)


def _create_new_sample(model, sample_name, sample_comment, sample_x, sample_y):
    item = QtGui.QStandardItem(f'{sample_name} at X {sample_x} Y {sample_y}')
    item.setDropEnabled(False)
    item.item_type = 'sample'
    item.setCheckable(True)
    item.setEditable(False)

    item.x = sample_x
    item.y = sample_y
    item.name = sample_name
    item.comment = sample_comment
    item.setIcon(icon_sample)

    parent = model.invisibleRootItem()
    parent.appendRow(item)


def _create_new_scan(model, scan_name, scan_type, scan_traj, scan_repeat, scan_delay):
    item = QtGui.QStandardItem(f'{scan_type} with {scan_traj}, {scan_repeat} times with {scan_delay} s delay')
    item.setDropEnabled(False)
    item.item_type = 'scan'
    item.scan_type = scan_type
    item.trajectory = scan_traj
    item.repeat = scan_repeat
    item.name = scan_name
    item.delay = scan_delay
    item.setCheckable(True)
    item.setEditable(False)
    item.setIcon(icon_scan)
    parent = model.invisibleRootItem()
    parent.appendRow(item)

def _clone_sample_item(item_sample):
    new_item_sample = QtGui.QStandardItem(item_sample.text())
    new_item_sample.item_type = 'sample'
    new_item_sample.x = item_sample.x
    new_item_sample.y = item_sample.y
    new_item_sample.name = item_sample.name
    new_item_sample.setIcon(icon_sample)
    return new_item_sample

def _clone_scan_item(item_scan):
    new_item_scan = QtGui.QStandardItem(item_scan.text())
    new_item_scan.item_type = 'scan'
    new_item_scan.trajectory = item_scan.trajectory
    new_item_scan.scan_type = item_scan.scan_type
    new_item_scan.repeat = item_scan.repeat
    new_item_scan.delay = item_scan.delay
    new_item_scan.name = item_scan.name
    return new_item_scan


class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])

            if orientation == Qt.Vertical:
                return str(self._data.index[section])
