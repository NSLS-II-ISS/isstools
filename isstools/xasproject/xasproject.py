from PyQt5 import QtCore
import pandas as pd
from larch import Group as xafsgroup
from larch_plugins.xafs import pre_edge, autobk, mback
from larch import Interpreter
import numpy as np



class XASDataSet:
    _md = {}
    _filename = ''
    _larch = Interpreter(with_plugins=False)

    def __init__(self, name=None, md=None, energy = None,mu=None, filename=None, datatype=None, *args, **kwargs):
        self.larch = xafsgroup()
        if md is not None:
            self._md = md
            if 'e0' in md:
                self.larch.e0 = int(md['e0'])
            elif 'edge' in md:
                edge = md['edge']
                self.larch.e0 = int(edge[edge.find('(') + 1: edge.find(')')])

        if mu is not None:
            self.larch.mu = np.array(mu)
        if energy is not None:
            self.larch.energy = np.array(energy)
        if filename is not None:
            self._filename = filename
        if name is not None:
            self.name = name
        if datatype is not None:
            self.datatype = datatype
        if mu is not None and energy is not None:
            self.subtract_background()
            self.deriv()
            self.extract_chi()

    def deriv(self):
        mu_deriv=np.diff(np.transpose(self.mu.values))/np.diff(self.energy)
        self.mu_deriv=mu_deriv[0]
        self.energy_deriv=(self.energy[1:]+self.energy[:-1])/2

    def flatten(self):
        step_index = int(np.argwhere(self.energy > self.e0)[0])
        zeros = np.zeros(step_index)
        ones = np.ones(self.energy.shape[0] - step_index)
        step = np.concatenate((zeros, ones), axis=0)
        diffline = (self.post_edge - self.pre_edge) / self.edge_step
        self.flat = self.norm + step * (1 - diffline)

    def subtract_background(self):
        pre_edge(self.larch, group=self.larch, _larch=self._larch)
        self.energy = self.larch.energy
        self.mu = self.larch.mu
        self.norm = self.larch.norm
        self.new_ds = False
        self.pre1 = self.larch.pre_edge_details.pre1
        self.pre2 = self.larch.pre_edge_details.pre2
        self.norm1 = self.larch.pre_edge_details.norm1
        self.norm2 = self.larch.pre_edge_details.norm2
        self.e0 = self.larch.e0
        self.pre_edge=self.larch.pre_edge
        self.post_edge = self.larch.post_edge
        self.edge_step = self.larch.edge_step
        self.flatten()


    def subtract_background_force(self):
        pre_edge(self.larch, group=self.larch, _larch=self._larch, e0=self.e0, pre1=self.pre1, pre2=self.pre2,
                                                                           norm1=self.norm1, norm2=self.norm2)
        self.norm = self.larch.norm
        self.e0 = self.larch.e0
        self.pre_edge=self.larch.pre_edge
        self.post_edge = self.larch.post_edge
        self.edge_step = self.larch.edge_step
        self.flatten()

    def extract_chi(self):
        autobk(self.larch, group=self.larch,  _larch=self._larch)
        self.k = self.larch.k
        self.chi = self.larch.chi
        self.bkg=self.larch.bkg

    def extract_chi_force(self):
        autobk(self.larch, group=self.larch, _larch=self._larch)
        self.k = self.larch.k
        self.chi = self.larch.chi
        self.bkg = self.larch.bkg


    @property
    def md(self):
        return self._md

    @md.setter
    def md(self, md):
        self._md = md
        if 'e0' in md:
            self.larch.e0 = int(md['e0'])
            pass
        elif 'edge' in md:
            edge = md['edge']
            self.larch.e0 = int(edge[edge.find('(') + 1: edge.find(')')])

    @property
    def mu(self):
        return self._mu

    @mu.setter
    def mu(self, mu):
        if hasattr(mu, 'values'):
            values = mu.values
        else:
            values = mu
        self._mu = pd.DataFrame(values, columns=['mu'])
        self.larch.mu = self._mu

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._filename = filename


class XASProject(QtCore.QObject):
    datasets_changed = QtCore.pyqtSignal(object)
    _datasets = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._datasets = []

    @property
    def datasets(self):
        return self._datasets

    def insert(self, dataset, index=None):
        if index is None:
            index = len(self._datasets)
        self._datasets.insert(index, dataset)
        self.datasets_changed.emit(self._datasets)

    def append(self, dataset):
        self._datasets.append(dataset)
        self.datasets_changed.emit(self._datasets)

    def removeDatasetIndex(self, index):
        del self._datasets[index]
        self.datasets_changed.emit(self._datasets)

    def removeDataset(self, dataset):
        self._datasets.remove(dataset)
        self.datasets_changed.emit(self._datasets)

    def __repr__(self):
        return f'{self._datasets}'.replace(', ', ',\n ')

    def __iter__(self):
        self._iterator = 0
        return self

    def __next__(self):
        if self._iterator < len(self.datasets):
            curr_iter = self._iterator
            self._iterator += 1
            return self.datasets[curr_iter]
        else:
            raise StopIteration

    def __getitem__(self, item):
        return self.datasets[item]