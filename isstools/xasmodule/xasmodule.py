import numpy as np
import matplotlib.pyplot as plt
import math
import os
from bluesky.global_state import gs
from databroker import (DataBroker as db, get_events, get_images,
                        get_table, get_fields, restream, process)
from datetime import datetime

class XASdata:
	def __init__(self, **kwargs):
		self.energy = np.array([])
		self.data = np.array([])
		self.encoder_file = ''
		self.i0_file = ''
		self.it_file = ''
		

class XASdataAbs(XASdata):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		#super(XASdata, self).__init__()
		self.i0 = np.array([])
		self.it = np.array([])

	def loadINTERPtrace(self, filename):
		array_timestamp=[]
		array_energy=[]
		array_i0=[]
		array_it=[]
		with open(str(filename)) as f:
			for line in f:
				current_line = line.split()
				if(current_line[0] != '#'):
					array_timestamp.append(float(current_line[0]))
					array_energy.append(float(current_line[1]))
					array_i0.append(float(current_line[2]))
					array_it.append(float(current_line[3]))
		return np.array(array_timestamp), np.array(array_energy), np.array(array_i0), np.array(array_it)

	def load(self, filename):
		self.timestamp, self.energy, self.i0, self.it = self.loadINTERPtrace(filename)

	def plot(self, ax, color='r'):
		result_chambers = np.copy(self.i0)
		result_chambers[:] = np.log(self.i0[:] / self.it[:])

		ax.hold(False)
		ax.plot(self.energy[:], result_chambers[:], color)
		ax.set_xlabel('Energy (eV)')
		ax.set_ylabel('log(i0 / it)')
		ax.grid(True)


class XASdataFlu(XASdata):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.i0 = np.array([])
		self.trigger = np.array([])
		self.iflu = np.array([])
		self.it = np.copy(self.iflu)
		self.trig_file = ''

	def load(self, encoder_trace = '', i0trace = '', iflutrace = '', trigtrace = ''):
		self.encoder_file = encoder_trace
		self.i0_file = i0trace
		self.it_file = iflutrace
		self.trig_file = trigtrace
		self.encoder = self.loadENCtrace(encoder_trace)
		self.energy = self.encoder
		for i in range(len(self.encoder)):
			self.energy[i, 1] = -12400 / (2 * 3.1356 * math.sin(math.radians((self.encoder[i, 1]/360000)+0.134)))
		self.i0 = self.loadADCtrace(i0trace)
		#self.trigger = self.loadTRIGtrace(trigtrace)
		self.iflu = self.loadADCtrace(iflutrace)
		self.it = np.copy(self.iflu)

	def plot(self, color='r'):
		result_chambers = self.i0_interp
		result_chambers[:,1] = (self.iflu_interp[:,1] / self.i0_interp[:,1])
		plt.plot(self.energy_interp[:,1], result_chambers[:,1], color)
		plt.xlabel('Energy (eV)')
		plt.ylabel('(iflu / i0)')
		plt.grid(True)
