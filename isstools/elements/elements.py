import pkg_resources
import json
from PyQt5 import QtWidgets, QtCore, QtGui
from isstools.dialogs.BasicDialogs import message_box, question_message_box


def get_element_dict():
    json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
    element_dict = {}

    for i in json.loads(json_data):
        element_dict[i['symbol']] = i
    return element_dict

element_dict = get_element_dict()

def _check_entry(el, edge, energy, name, row):


    info = f'Proposal: {name}, row: {row}, element: {el}, edge: {edge}, energy: {energy}'
    if el in element_dict.keys():
        if edge in element_dict[el].keys():
            if abs(energy - float(
                    element_dict[el][edge])) < 10:  # provided energy must be within 10 eV from the xray DB
                if (energy > 4900) and (energy < 32000):
                    return True
                else:
                    message_box('Energy outside of feasible range',
                                ('Warning\nAn entry with energy outside of feasible range found!\n' +
                                 'This measurement will be skipped.\n' +
                                 info))
            else:
                message_box('Invalid energy',
                            ('Warning\nAn entry with invalid energy was found!\n' +
                             'This measurement will be skipped.\n' +
                             info))
        else:
            message_box('Edge not found',
                        ('Warning\nAn entry with invalid edge was found!\n' +
                         'This measurement will be skipped.\n' +
                         info))
    else:
        message_box('Element not found',
                    ('Warning\nAn entry with invalid element was found!\n' +
                     'This measurement will be skipped.\n' +
                     info))
    return False



def remove_ev_from_energy_str(energy):
    if 'ev' in energy:
        return energy.replace('ev', '')
    if 'eV' in energy:
        return energy.replace('eV', '')
    if 'EV' in energy:
        return energy.replace('EV', '')
    return energy



_edges_L1 = ['L1', 'L-1', 'L_1', 'L-I', 'L_I']
_edges_L2 = ['L2', 'L-2', 'L_2', 'L-II', 'L_II']
_edges_L3 = ['L3', 'L-3', 'L_3', 'L-III', 'L_III']
def remove_edge_from_edge_str(edge):
    if 'K' in edge:
        return 'K'
    if any([suf in edge for suf in _edges_L1]):
        return 'L1'
    if any([suf in edge for suf in _edges_L2]):
        return 'L2'
    if any([suf in edge for suf in _edges_L3]):
        return 'L3'
    return edge

def clean_el_str(el):
    for i in element_dict.keys():
        if i in el:
            return i
    return el




class TreeView(QtWidgets.QTreeView):
    def __init__(self, parent, accepted_type, unique_elements=True):
        QtWidgets.QTreeView.__init__(self, parent)
        self.accepted_type = accepted_type
        self.unique_elements = unique_elements
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def startDrag(self, dropAction):
        mime = QtCore.QMimeData()
        mime.setData('accepted_type', self.accepted_type.encode('utf-8'))
        index = self.currentIndex()
        item = index.model().itemFromIndex(index)
        mime.setText(item.text())
        #mime.setData('application/x-item', '???')

        #print('Start dragging')
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.exec(QtCore.Qt.CopyAction)#start(QtCore.Qt.CopyAction)#(QtCore.Qt.CopyAction)

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
        #QtWidgets.QTreeView.dropEvent(self, event)
        #if event.isAccepted():
        #    print('dropEvent', hasattr(self, 'x'))
        #print('Formats: {}'.format(event.mimeData().formats()))
        #print('Mime: {}'.format(event.mimeData().data('application/x-qstandarditemmodeldatalist')))
        #data = event.mimeData().data('application/x-qabstractitemmodeldatalist')
        print('here')

        '''
        exists = False
        curr_item_text = event.mimeData().text()
        if self.unique_elements:
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
            QtWidgets.QTreeView.dropEvent(self, event)
        '''

