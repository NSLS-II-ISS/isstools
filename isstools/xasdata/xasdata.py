import numpy as np
import matplotlib.pyplot as plt
import math
import os
from bluesky.global_state import gs
from databroker import (DataBroker as db, get_events, get_images,
                        get_table, get_fields, restream, process)
from datetime import datetime
from isstools.conversions import xray
from subprocess import call
import re
import collections

class XASdata:
    def __init__(self, **kwargs):
        self.energy = np.array([])
        self.data = np.array([])
        self.encoder_file = ''
        self.i0_file = ''
        self.it_file = ''
        self.ir_file = ''
        self.iff_file = ''
        self.data_manager = XASDataManager()
        self.header_read = ''

    def loadADCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out=[]
        with open(filepath + str(filename)) as f:
            for line in f:
                current_line = line.split()
                current_line[3] = int(current_line[3],0) >> 8
                if current_line[3] > 0x1FFFF:
                    current_line[3] -= 0x40000
                current_line[3] = float(current_line[3]) * 7.62939453125e-05
                array_out.append(
                        [int(current_line[0])+1e-9*int(current_line[1]), current_line[3], int(current_line[2])])
        return np.array(array_out)

    def loadENCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out = []
        with open(filepath + str(filename)) as f:
            for line in f:  # read rest of lines
                current_line = line.split()
                current_line[2] = int(current_line[2])
                if current_line[2] > 0:
                    current_line[2] = -(current_line[2] ^ 0xffffff - 1)
                array_out.append([int(current_line[0])+1e-9*int(current_line[1]), current_line[2], int(current_line[3])])
        return np.array(array_out)

    def loadTRIGtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out = []
        with open(filepath + str(filename)) as f:
            for line in f:  # read rest of lines
                current_line = line.split()
                if(int(current_line[3]) % 2 == 0):
                    array_out.append([int(current_line[0])+1e-9*int(current_line[1]), int(current_line[3])])
        return np.array(array_out)

    def loadINTERPtrace(self, filename):
        array_timestamp=[]
        array_energy=[]
        array_i0=[]
        array_it=[]
        array_ir=[]
        array_iff=[]
        with open(str(filename)) as f:
            for line in f:
                current_line = line.split()
                if(current_line[0] != '#'):
                    array_timestamp.append(float(current_line[0]))
                    array_energy.append(float(current_line[1]))
                    array_i0.append(float(current_line[2]))
                    array_it.append(float(current_line[3]))
                    if len(current_line) >= 5:
                        array_ir.append(float(current_line[4]))
                    if len(current_line) >= 6:
                        array_iff.append(float(current_line[5]))
        self.header_read = self.read_header(filename)
        ts, energy, i0, it, ir, iff = np.array(array_timestamp), np.array(array_energy), np.array(array_i0), np.array(array_it), np.array(array_ir), np.array(array_iff)

        # Trying to make it compatible with old files (iff = [1, 1, ..., 1, 1]):
        if not len(iff):
            iff = np.ones(len(i0))
        return np.concatenate(([ts], [energy])).transpose(), np.concatenate(([ts], [i0])).transpose(),np.concatenate(([ts], [it])).transpose(), np.concatenate(([ts], [ir])).transpose(), np.concatenate(([ts], [iff])).transpose()
        
    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line)]



class XASdataAbs(XASdata):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.i0 = np.array([])
        self.it = np.array([])
        self.ir = np.array([])
        self.iff = np.array([])

    def process(self, encoder_trace, i0trace, ittrace, irtrace = '', ifftrace = '', i0offset = 0, itoffset = 0, iroffset = 0, iffoffset = 0):
        self.load(encoder_trace, i0trace, ittrace, irtrace, ifftrace, i0offset, itoffset, iroffset, iffoffset)
        self.interpolate()
        self.plot()

    def load(self, encoder_trace, i0trace, ittrace, irtrace = '', ifftrace = '', i0offset = 0, itoffset = 0, iroffset = 0, iffoffset = 0, angleoffset = 0):
        self.encoder_file = encoder_trace
        self.i0_file = i0trace
        self.it_file = ittrace
        self.ir_file = irtrace
        self.iff_file = ifftrace
        self.encoder = self.loadENCtrace(encoder_trace)
        self.energy = self.encoder
        self.energy[:, 1] = xray.encoder2energy(self.encoder[:, 1], -angleoffset) #-12400 / (2 * 3.1356 * np.sin((np.pi / 180) * ((self.encoder[:, 1]/360000) + 0)))
        self.i0 = self.loadADCtrace(i0trace)
        self.it = self.loadADCtrace(ittrace)
        self.ir = self.loadADCtrace(irtrace)
        self.iff = self.loadADCtrace(ifftrace)
        self.i0[:, 1] = self.i0[:, 1] - i0offset
        self.it[:, 1] = self.it[:, 1] - itoffset
        self.ir[:, 1] = self.ir[:, 1] - iroffset
        self.iff[:, 1] = self.iff[:, 1] - iffoffset

    def loadInterpFile(self, filename):
        self.energy_interp, self.i0_interp, self.it_interp, self.ir_interp , self.iff_interp = self.loadINTERPtrace(filename)
        matrix = np.array([self.energy_interp[:,1], self.i0_interp[:,1], self.it_interp[:,1], self.ir_interp[:,1], self.iff_interp[:,1]]).transpose()
        sorted_matrix = self.data_manager.sort_data(matrix, 0) 
        self.energy_interp[:,1] = sorted_matrix[:,0]
        self.i0_interp[:,1] = sorted_matrix[:,1]
        self.it_interp[:,1] = sorted_matrix[:,2]
        self.ir_interp[:,1] = sorted_matrix[:,3]
        self.iff_interp[:,1] = sorted_matrix[:,4]

        len_to_erase = int(np.round(0.015 * len(self.i0_interp)))
        self.energy_interp = self.energy_interp[len_to_erase:]
        self.i0_interp = self.i0_interp[len_to_erase:]
        self.it_interp = self.it_interp[len_to_erase:]
        self.ir_interp = self.ir_interp[len_to_erase:]
        self.iff_interp = self.iff_interp[len_to_erase:]

    def interpolate(self):
        min_timestamp = np.array([self.i0[0,0], self.it[0,0], self.ir[0,0], self.iff[0,0], self.encoder[0,0]]).max()
        max_timestamp = np.array([self.i0[len(self.i0)-1,0], self.it[len(self.it)-1,0], self.ir[len(self.ir)-1,0], self.iff[len(self.iff)-1,0], self.encoder[len(self.encoder)-1,0]]).min()
        interval = self.i0[1,0] - self.i0[0,0]
        timestamps = np.arange(min_timestamp, max_timestamp, interval)
        self.i0_interp = np.array([timestamps, np.interp(timestamps, self.i0[:,0], self.i0[:,1])]).transpose()
        self.it_interp = np.array([timestamps, np.interp(timestamps, self.it[:,0], self.it[:,1])]).transpose()
        self.ir_interp = np.array([timestamps, np.interp(timestamps, self.ir[:,0], self.ir[:,1])]).transpose()
        self.iff_interp = np.array([timestamps, np.interp(timestamps, self.iff[:,0], self.iff[:,1])]).transpose()
        self.energy_interp = np.array([timestamps, np.interp(timestamps, self.energy[:,0], self.energy[:,1])]).transpose()

    def get_plot_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        result_chambers = np.copy(self.i0_interp)

        if len(plotting_dic) > 0:
            num = plotting_dic['numerator']
            den = plotting_dic['denominator']
            log = plotting_dic['log']
            division = num[:,1]/den[:,1]
            if log:
                division = np.log(np.abs(division))
            result_chambers[:,1] = division

        else:
            result_chambers[:,1] = np.log(self.i0_interp[:,1] / self.it_interp[:,1])
        
        #ax.plot(self.energy_interp[:,1], result_chambers[:,1], color)
        #ax.grid(True)
        if 'xlabel' in dir(ax):
            xlabel = 'Energy (eV)'
            ylabel = 'log(i0 / it)'
        else:
            xlabel = 'Energy (eV)'
            ylabel = 'log(i0 / it)'

        return [self.energy_interp[:,1], result_chambers[:,1], color, xlabel, ylabel, ax]


    def plot(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        result_chambers = np.copy(self.i0_interp)

        if len(plotting_dic) > 0:
            num = plotting_dic['numerator']
            den = plotting_dic['denominator']
            log = plotting_dic['log']
            division = num[:,1]/den[:,1]
            if log:
                division = np.log(np.abs(division))
            result_chambers[:,1] = division

        else:
            result_chambers[:,1] = np.log(self.i0_interp[:,1] / self.it_interp[:,1])
        
        ax.plot(self.energy_interp[:,1], result_chambers[:,1], color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('log(i0 / it)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('log(i0 / it)')

    def export_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/', uid = ''):
        suffix = '.txt'
        fn = filepath + filename + suffix
        repeat = 1
        while(os.path.isfile(fn)):
            repeat += 1
            fn = filepath + filename + '-' + str(repeat) + suffix
        if(not uid):
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time, trajectory_name = '', '', '', '', '', '', '', '', '', '', ''
        else:
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time = db[uid]['start']['PI'], db[uid]['start']['PROPOSAL'], db[uid]['start']['SAF'], db[uid]['start']['comment'], db[uid]['start']['year'], db[uid]['start']['cycle'], db[uid]['start']['scan_id'], db[uid]['start']['uid'], db[uid]['start']['time'], db[uid]['stop']['time']
            human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
            human_stop_time = str(datetime.fromtimestamp(stop_time).strftime(' %m/%d/%Y  %H:%M:%S'))
            human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))
            if hasattr(db[uid]['start'], 'trajectory_name'):
                trajectory_name = db[uid]['start']['trajectory_name']
            else:
                trajectory_name = ''
        
        np.savetxt(fn, np.array([self.energy_interp[:,0], self.energy_interp[:,1], 
                    self.i0_interp[:,1], self.it_interp[:,1], self.ir_interp[:,1], self.iff_interp[:,1]]).transpose(), fmt='%17.6f %12.6f %10.6f %10.6f %10.6f %10.6f', 
                    delimiter=" ", header = 'Timestamp (s)   En. (eV)     i0 (V)      it(V)       ir(V)       iff(V)', comments = '# Year: {}\n# Cycle: {}\n# SAF: {}\n# PI: {}\n# PROPOSAL: {}\n# Scan ID: {}\n# UID: {}\n# Trajectory name: {}\n# Start time: {}\n# Stop time: {}\n# Total time: {}\n#\n# '.format(year, cycle, saf, pi, proposal, scan_id, real_uid, trajectory_name, human_start_time, human_stop_time, human_duration))
        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn


    def bin_equal(self):
        self.data_manager.process_equal(self.i0_interp[:,0], 
                                  self.energy_interp[:,1],
                                  self.i0_interp[:,1],
                                  self.it_interp[:,1], 
                                  self.ir_interp[:,1],
                                  self.iff_interp[:,1])

    def bin(self, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):
        self.data_manager.process(self.i0_interp[:,0], 
                                  self.energy_interp[:,1],
                                  self.i0_interp[:,1],
                                  self.it_interp[:,1], 
                                  self.ir_interp[:,1],
                                  self.iff_interp[:,1],
                                  e0, edge_start, edge_end,
                                  preedge_spacing, xanes, exafsk)


class XASdataFlu(XASdata):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.i0 = np.array([])
        self.trigger = np.array([])
        self.iflu = np.array([])
        self.it = np.array([])
        self.ir = np.array([])
        self.trig_file = ''

    def process(self, encoder_trace, i0trace, iflutrace, irtrace = '', trigtrace = '', i0offset = 0, ifluoffset = 0, iroffset = 0):
        self.load(encoder_trace, i0trace, iflutrace, irtrace, trigtrace, i0offset, ifluoffset, iroffset)
        self.interpolate()
        self.plot()

    def load(self, encoder_trace, i0trace, iflutrace, irtrace = '', ifftrace = '', trigtrace = '', i0offset = 0, ifluoffset = 0, iroffset = 0, iffoffset = 0, angleoffset = 0):
        self.encoder_file = encoder_trace
        self.i0_file = i0trace
        self.it_file = iflutrace
        self.ir_file = irtrace
        self.trig_file = trigtrace
        self.encoder = self.loadENCtrace(encoder_trace)
        self.energy = np.copy(self.encoder)
        #self.energy[:, 1] = xray.encoder2energy(self.encoder[:, 1], 0.041)
        self.energy[:, 1] = xray.encoder2energy(self.encoder[:, 1], -angleoffset)
        self.i0 = self.loadADCtrace(i0trace)
        self.i0[:, 1] = self.i0[:, 1] - i0offset
        self.ir = self.loadADCtrace(irtrace)
        self.ir[:, 1] = self.ir[:, 1] - iroffset
        self.iflu = self.loadADCtrace(iflutrace)
        self.iflu[:, 1] = self.iflu[:, 1] - ifluoffset
        self.trigger = self.loadTRIGtrace(trigtrace)
        self.it = np.copy(self.iflu)

    def loadInterpFile(self, filename):
        self.energy_interp, self.i0_interp, self.it_interp, self.ir_interp, self.iff_interp = self.loadINTERPtrace(filename)
        #matrix = np.array([self.energy_interp, self.i0_interp, self.it_interp, self.ir_interp]).transpose()
        #sorted_matrix = self.data_manager.sort_data(matrix, 0) 
        #self.energy_interp = sorted_matrix[0]
        #self.i0_interp = sorted_matrix[1]
        #self.it_interp = sorted_matrix[2]
        #self.ir_interp = sorted_matrix[3]

    def interpolate(self):
        i0_copy = np.copy(self.i0)
        iflu_copy = np.copy(self.iflu)
        ir_copy = np.copy(self.ir)
        energy_copy = np.copy(self.energy)
        i0_interp = []
        iflu_interp = []
        ir_interp = []
        energy_interp = []
        trigger_interp = []
        timestamps = []

        for i in range(len(self.trigger) - 1):

            condition1 = (self.trigger[i,0] <= i0_copy[:,0]) == (self.trigger[i + 1,0] > i0_copy[:,0])
            interval1 = np.extract(condition1, i0_copy[:,0])

            condition2 = (self.trigger[i,0] <= iflu_copy[:,0]) == (self.trigger[i + 1,0] > iflu_copy[:,0])
            interval2 = np.extract(condition2, iflu_copy[:,0])

            condition3 = (self.trigger[i,0] <= energy_copy[:,0]) == (self.trigger[i + 1,0] > energy_copy[:,0])
            interval3 = np.extract(condition3, energy_copy[:,0])

            condition4 = (self.trigger[i,0] <= ir_copy[:,0]) == (self.trigger[i + 1,0] > ir_copy[:,0])
            interval4 = np.extract(condition4, ir_copy[:,0])

            if len(interval1) and len(interval2) and len(interval3):
                interval_mean_i0 = np.mean(np.extract(condition1, i0_copy[:,1]))
                i0_interp.append(interval_mean_i0)
                i0_pos_high = np.where( i0_copy[:,0] == interval1[len(interval1) - 1] )[0][0]
                i0_copy = i0_copy[i0_pos_high + 1:len(i0_copy)]


                interval_mean_iflu = np.mean(np.extract(condition2, iflu_copy[:,1]))
                iflu_interp.append(interval_mean_iflu)
                iflu_pos_high = np.where( iflu_copy[:,0] == interval2[len(interval2) - 1] )[0][0]
                iflu_copy = iflu_copy[iflu_pos_high + 1:len(iflu_copy)]


                interval_mean_energy = np.mean(np.extract(condition3, energy_copy[:,1]))
                energy_interp.append(interval_mean_energy)
                energy_pos_high = np.where( energy_copy[:,0] == interval3[len(interval3) - 1] )[0][0]
                energy_copy = energy_copy[energy_pos_high + 1:len(energy_copy)]


                interval_mean_ir = np.mean(np.extract(condition4, ir_copy[:,1]))
                ir_interp.append(interval_mean_ir)
                ir_pos_high = np.where( ir_copy[:,0] == interval4[len(interval4) - 1] )[0][0]
                ir_copy = ir_copy[ir_pos_high + 1:len(ir_copy)]

                timestamps.append((self.trigger[i, 0] + self.trigger[i + 1, 0])/2)
                trigger_interp.append(self.trigger[i, 1])

        self.i0_interp = np.array([timestamps, i0_interp]).transpose()
        self.iflu_interp = np.array([timestamps, iflu_interp]).transpose()
        self.ir_interp = np.array([timestamps, ir_interp]).transpose()
        #self.it_interp = np.copy(self.iflu_interp)
        self.energy_interp = np.array([timestamps, energy_interp]).transpose()
        self.trigger_interp = np.array([timestamps, trigger_interp]).transpose()


    def plot(self, ax=plt, color='r'):
        result_chambers = np.copy(self.i0_interp)
        result_chambers[:,1] = (self.iflu_interp[:,1] / self.i0_interp[:,1])

        ax.plot(self.energy_interp[:,1], result_chambers[:,1], color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('(iflu / i0)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('(iflu / i0)')


    def export_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/', uid = ''):
        suffix = '.txt'
        fn = filepath + filename + suffix
        repeat = 1
        while(os.path.isfile(fn)):
            repeat += 1
            fn = filepath + filename + '-' + str(repeat) + suffix
        if(not uid):
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time, trajectory_name = '', '', '', '', '', '', '', '', '', '', ''
        else:
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time = db[uid]['start']['PI'], db[uid]['start']['PROPOSAL'], db[uid]['start']['SAF'], db[uid]['start']['comment'], db[uid]['start']['year'], db[uid]['start']['cycle'], db[uid]['start']['scan_id'], db[uid]['start']['uid'], db[uid]['start']['time'], db[uid]['stop']['time']
            human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
            human_stop_time = str(datetime.fromtimestamp(stop_time).strftime(' %m/%d/%Y  %H:%M:%S'))
            human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))

            if hasattr(db[uid]['start'], 'trajectory_name'):
                trajectory_name = db[uid]['start']['trajectory_name']
            else:
                trajectory_name = ''

        
        np.savetxt(fn, np.array([self.energy_interp[:,0], self.energy_interp[:,1], 
                    self.i0_interp[:,1], self.iflu_interp[:,1], self.ir_interp[:,1]]).transpose(), fmt='%17.6f %12.6f %10.6f %10.6f %10.6f', 
                    delimiter=" ", header = 'Timestamp (s)   En. (eV)   i0 (V)    iflu(V)   ir(V)', comments = '# Year: {}\n# Cycle: {}\n# SAF: {}\n# PI: {}\n# PROPOSAL: {}\n# Scan ID: {}\n# UID: {}\n# Trajectory name: {}\n# Start time: {}\n# Stop time: {}\n# Total time: {}\n#\n# '.format(year, cycle, saf, pi, proposal, scan_id, real_uid, trajectory_name, human_start_time, human_stop_time, human_duration))
        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn



    def export_trace_xia(self, parsed_xia_array, filename, filepath = '/GPFS/xf08id/Sandbox/', uid = ''):
        parsed_xia_array = np.array(parsed_xia_array)
        suffix = '.txt'
        fn = filepath + filename + suffix
        repeat = 1
        while(os.path.isfile(fn)):
            repeat += 1
            fn = filepath + filename + '-' + str(repeat) + suffix
        if(not uid):
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time, trajectory_name = '', '', '', '', '', '', '', '', '', '', ''
        else:
            pi, proposal, saf, comment, year, cycle, scan_id, real_uid, start_time, stop_time = db[uid]['start']['PI'], db[uid]['start']['PROPOSAL'], db[uid]['start']['SAF'], db[uid]['start']['comment'], db[uid]['start']['year'], db[uid]['start']['cycle'], db[uid]['start']['scan_id'], db[uid]['start']['uid'], db[uid]['start']['time'], db[uid]['stop']['time']
            human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
            human_stop_time = str(datetime.fromtimestamp(stop_time).strftime(' %m/%d/%Y  %H:%M:%S'))
            human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))

            if hasattr(db[uid]['start'], 'trajectory_name'):
                trajectory_name = db[uid]['start']['trajectory_name']
            else:
                trajectory_name = ''
        
        np.savetxt(fn, np.array([self.energy_interp[:,0], self.energy_interp[:,1], 
                    self.i0_interp[:,1], self.iflu_interp[:,1], parsed_xia_array]).transpose(), fmt='%17.6f %12.6f %f %f', 
                    delimiter=" ", header = 'Timestamp (s)   En. (eV)  i0 (V)    iflu(V)   xia', comments = '# Year: {}\n# Cycle: {}\n# SAF: {}\n# PI: {}\n# PROPOSAL: {}\n# Scan ID: {}\n# UID: {}\n# Trajectory name: {}\n# Start time: {}\n# Stop time: {}\n# Total time: {}\n#\n# '.format(year, cycle, saf, pi, proposal, scan_id, real_uid, trajectory_name, human_start_time, human_stop_time, human_duration))
        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn

    def export_trig_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/'):
        np.savetxt(filepath + filename + suffix, self.energy_interp[:,1], fmt='%f', delimiter=" ")
        call(['setfacl', '-m', 'g:iss-staff:rwX', filepath + filename + suffix])
        call(['chmod', '770', filepath + filename + suffix])


class XASdataGeneric(XASdata):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arrays = {}
        self.interp_arrays = {}
        self.db = db
        self.uid = ''
        
    def process(self, uid):
        self.load(uid)
        self.uid = uid
        self.interpolate()
        #sself.plot()

    def load(self, uid):
        self.arrays = {}
        self.interp_arrays = {}
        self.uid = uid
        has_encoder = False
        for i in self.db[uid]['descriptors']:
            if 'filename' in i['data_keys'][i['name']]:
                name = i['name']
                if name == 'pb9_enc1' or name == 'hhm_theta':
                    has_encoder = name
                if 'devname' in i['data_keys'][i['name']]:
                    name = i['data_keys'][i['name']]['devname']
                    if name == 'hhm_theta':
                        has_encoder = name
                    
                if i['data_keys'][i['name']]['source'] == 'pizzabox-di-file':
                    data = self.loadTRIGtrace(i['data_keys'][i['name']]['filename'], '')
                if i['data_keys'][i['name']]['source'] == 'pizzabox-adc-file':
                    data = self.loadADCtrace(i['data_keys'][i['name']]['filename'], '')
                    if i['name'] + ' offset' in self.db[uid]['start']:
                        data[:, 1] = data[:, 1] - self.db[uid]['start'][i['name'] + ' offset']
                if i['data_keys'][i['name']]['source'] == 'pizzabox-enc-file':
                    data = self.loadENCtrace(i['data_keys'][i['name']]['filename'], '')
                self.arrays[name] = data
        
        if has_encoder is not False:
            energy = np.copy(self.arrays.get(has_encoder))
            if 'angle_offset' in self.db[uid]['start']:
                energy[:, 1] = xray.encoder2energy(energy[:, 1], - float(self.db[uid]['start']['angle_offset']))
            del self.arrays[has_encoder]
            self.arrays['energy'] = energy

        
    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line)]

    def loadInterpFile(self, filename):
        self.arrays = {}
        self.interp_arrays = {}

        header = self.read_header(filename)
        self.uid = header[header.find('UID') + 5: header.find('\n', header.find('UID'))]

        keys = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        timestamp_index = -1
        if 'Timestamp (s)' in keys:
            timestamp_index = keys.index('Timestamp (s)')
        elif 'timestamp' in keys:
            timestamp_index = keys.index('timestamp')
        
        matrix = np.loadtxt(filename)
        for i in range(matrix.shape[1]):
            if i != timestamp_index:
                self.interp_arrays[keys[i]] = np.array([matrix[:, timestamp_index], matrix[:, i]]).transpose()
        self.interp_arrays['1'] = np.array([matrix[:, timestamp_index], np.ones(len(matrix[:, 0]))]).transpose()


    def interpolate(self, key_base = 'i0'):
        min_timestamp = max([self.arrays.get(key)[0, 0] for key in self.arrays])
        max_timestamp = min([self.arrays.get(key)[len(self.arrays.get(key)) - 1, 0] for key in self.arrays])
        
        try:
            if key_base not in self.arrays.keys():
                raise ValueError('Could not find "{}" in the loaded scan. Pick another key_base for the interpolation.'.format(key_base))
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return
        
        timestamps = self.arrays[key_base][:,0]
        
        condition = timestamps < min_timestamp
        timestamps = timestamps[np.sum(condition):]
        
        condition = timestamps > max_timestamp
        timestamps = timestamps[: len(timestamps) - np.sum(condition)]
        
        for key in self.arrays.keys():
            self.interp_arrays[key] = np.array([timestamps, np.interp(timestamps, self.arrays.get(key)[:,0], self.arrays.get(key)[:,1])]).transpose()
        self.interp_arrays['1'] = np.array([timestamps, np.ones(len(self.interp_arrays[list(self.interp_arrays.keys())[0]]))]).transpose()


    def get_plot_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass


    def plot(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass

    def export_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/', overwrite = False):
        suffix = '.txt'
        fn = filepath + filename + suffix
        if not overwrite:
            repeat = 1
            while(os.path.isfile(fn)):
                repeat += 1
                fn = filepath + filename + '-' + str(repeat) + suffix

        pi = self.db[self.uid]['start']['PI']
        proposal = self.db[self.uid]['start']['PROPOSAL']
        saf = self.db[self.uid]['start']['SAF']
        comment = self.db[self.uid]['start']['comment']
        year = self.db[self.uid]['start']['year']
        cycle = self.db[self.uid]['start']['cycle']
        scan_id = self.db[self.uid]['start']['scan_id']
        real_uid = self.db[self.uid]['start']['uid']
        start_time = self.db[self.uid]['start']['time']
        stop_time = self.db[self.uid]['stop']['time']
        human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_stop_time = str(datetime.fromtimestamp(stop_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))
        if hasattr(self.db[self.uid]['start'], 'trajectory_name'):
            trajectory_name = self.db[self.uid]['start']['trajectory_name']
        else:
            trajectory_name = ''
        copy_interp = collections.OrderedDict(sorted(self.interp_arrays.items())).copy()
        #copy_interp = self.interp_arrays.copy()
        if '1' in copy_interp:
            del copy_interp['1']
        keys = copy_interp.keys()
        matrix = [self.interp_arrays[list(self.interp_arrays.keys())[0]][:,0]]
        energy_header = ''
        if 'energy' in copy_interp.keys():
            matrix.append(copy_interp['energy'][:,1])
            del copy_interp['energy']
            energy_header = 'energy'
        elif 'En. (eV)' in copy_interp.keys():
            matrix.append(copy_interp['En. (eV)'][:,1])
            del copy_interp['En. (eV)']
            energy_header = 'En. (eV)'

        i0_header = ''
        if 'i0' in copy_interp.keys():
            matrix.append(copy_interp['i0'][:,1])
            del copy_interp['i0']
            i0_header = 'i0'
        elif 'i0 (V)' in copy_interp.keys():
            matrix.append(copy_interp['i0 (V)'][:,1])
            del copy_interp['i0 (V)']
            i0_header = 'i0 (V)'

        it_header = ''
        if 'it' in copy_interp.keys():
            matrix.append(copy_interp['it'][:,1])
            del copy_interp['it']
            it_header = 'it'
        elif 'it(V)' in copy_interp.keys():
            matrix.append(copy_interp['it(V)'][:,1])
            del copy_interp['it(V)']
            it_header = 'it(V)'

        ir_header = ''
        if 'ir' in copy_interp.keys():
            matrix.append(copy_interp['ir'][:,1])
            del copy_interp['ir']
            ir_header = 'ir'
        elif 'ir(V)' in copy_interp.keys():
            matrix.append(copy_interp['ir(V)'][:,1])
            del copy_interp['ir(V)']
            ir_header = 'ir(V)'

        iff_header = ''
        if 'iff' in copy_interp.keys():
            matrix.append(copy_interp['iff'][:,1])
            del copy_interp['iff']
            iff_header = 'iff'
        elif 'iff(V)' in copy_interp.keys():
            matrix.append(copy_interp['iff(V)'][:,1])
            del copy_interp['iff(V)']
            iff_header = 'iff(V)'
        

        for key in copy_interp.keys():
            matrix.append(copy_interp[key][:,1])
        matrix = np.array(matrix).transpose()

        fmt = ' '.join(['%12.6f' for key in copy_interp.keys()])
        header = '  '.join(copy_interp.keys())
        if iff_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(iff_header, header)
        if ir_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(ir_header, header)
        if it_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(it_header, header)
        if i0_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(i0_header, header)
        if energy_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(energy_header, header)
        fmt = '{} {}'.format('%17.6f', fmt)
        header = '{}  {}'.format('timestamp', header)

        np.savetxt(fn, 
                   matrix, 
                   fmt=fmt, 
                   delimiter=" ", 
                   header = header,
                   comments = '# Year: {}\n'\
                              '# Cycle: {}\n'\
                              '# SAF: {}\n'\
                              '# PI: {}\n'\
                              '# PROPOSAL: {}\n'\
                              '# Scan ID: {}\n'\
                              '# UID: {}\n'\
                              '# Trajectory name: {}\n'\
                              '# Start time: {}\n'\
                              '# Stop time: {}\n'\
                              '# Total time: {}\n#\n# '.format(year, 
                                                               cycle, 
                                                               saf, 
                                                               pi, 
                                                               proposal, 
                                                               scan_id, 
                                                               real_uid, 
                                                               trajectory_name, 
                                                               human_start_time, 
                                                               human_stop_time, 
                                                               human_duration))
        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn

    def get_energy_string(self, possibilities = ['energy', 'En. (eV)']):

        try:
            energy_string = ''
            for string in possibilities:
                if string in self.interp_arrays.keys():
                    return string
            raise ValueError('Could not find energy'\
                             ' in the header of the'\
                             ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1



    def bin_equal(self, en_spacing = 2):

        try:
            energy_string = ''
            if 'energy' in self.interp_arrays.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_arrays.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy'\
                                 ' in the header of the'\
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1

        return self.data_manager.process_equal_gen(self.interp_arrays,
                                            energy_string = energy_string,
                                            delta_en = en_spacing)

    def bin(self, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):

        try:
            energy_string = ''
            if 'energy' in self.interp_arrays.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_arrays.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy'\
                                 ' in the header of the'\
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return    

        return self.data_manager.process_gen(self.interp_arrays, 
                                             e0, edge_start, edge_end,
                                             preedge_spacing, xanes, 
                                             exafsk, energy_string = energy_string)













class XASDataManager:
    def __init__(self, *args, **kwargs):
        self.data_arrays = {}
        self.binned_eq_arrays = {}
        self.binned_arrays = {}

    def delta_energy(self, array):
        diff = np.diff(array)
        diff = np.concatenate((diff,[diff[len(diff)-1]]))
        out = (np.concatenate(([diff[0]], diff[:len(diff)-1])) + diff)/2
        return out
    
    def sort_data(self, matrix, column_to_sort):
        return matrix[matrix[:,column_to_sort].argsort()]
    
    def energy_grid_equal(self, array, interval):
        return np.arange(np.min(array), np.max(array) + interval/2, interval)
    
    def energy_grid(self, array, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):
        preedge = np.arange(np.min(array), edge_start, preedge_spacing)
        edge = np.arange(edge_start, edge_end, xanes)

        eenergy = xray.k2e(xray.e2k(edge_end, e0), e0)
        postedge = np.array([])

        while(eenergy < np.max(array)):
            kenergy = xray.e2k(eenergy, e0)
            kenergy += exafsk
            eenergy = xray.k2e(kenergy, e0)
            postedge = np.append(postedge, eenergy)

        return np.append(np.append(preedge, edge), postedge)

    def get_k_data(self, e0, edge_end, exafsk, y_data, energy_array, en_orig, data_orig, pow = 1):
        e_interval = self.get_k_interval(energy_array, e0, e0 + edge_end, exafsk)
        k_interval = xray.e2k(e_interval, e0) #e0 + edge_end)

        condition = en_orig >= e0 + edge_end 
        en_orig = np.extract(condition, en_orig)
        data_orig = np.extract(condition, data_orig)
        polyfit = np.polyfit(en_orig, data_orig, 2) #2 is ok?
        p = np.poly1d(polyfit)
        calibration = p(e_interval)

        y_data = y_data[-len(k_interval):] - calibration
        data = y_data[-len(k_interval):] * (k_interval ** pow)
        return np.array([k_interval, data])


    def get_k_interval(self, energy_array, e0, edge_end, exafsk):
        iterator = exafsk
        kenergy = 0
        postedge = np.array([])
        
        while(kenergy + edge_end < np.max(energy_array)):
            kenergy = xray.k2e(iterator, e0) - e0
            postedge = np.append(postedge, edge_end + kenergy)
            iterator += exafsk

        return postedge
 
    def get_plotk_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        if len(plotting_dic) > 0:
            self.num_orig = plotting_dic['original_numerator']
            self.den_orig = plotting_dic['original_denominator']
            self.log = plotting_dic['log']
            division = self.num_orig/self.den_orig
            if self.log:
                division = np.log(division)
            self.abs = division

        else:
            self.abs = np.log(self.i0_interp / self.it_interp)
        
        #ax.plot(self.en_grid, self.abs, color)
        #ax.grid(True)
        xlabel = 'Energy (eV)'
        ylabel = 'Log(i0 / it)'

        return [self.en_grid, self.abs, color, xlabel, ylabel, ax]

    def plot_k_data(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        if len(plotting_dic) > 0:
            self.num_orig = plotting_dic['original_numerator']
            self.den_orig = plotting_dic['original_denominator']
            self.log = plotting_dic['log']
            division = self.num_orig/self.den_orig
            if self.log:
                division = np.log(division)
            self.abs = division

        else:
            self.abs = np.log(self.i0_interp / self.it_interp)
        
        ax.plot(self.en_grid, self.abs, color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('Log(i0 / it)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('Log(i0 / it)')    

    def gauss(self, x, fwhm, x0):
        sigma = fwhm / (2 * ((np.log(2)) ** (1/2)))
        a = 1/(sigma * ((2 * np.pi) ** (1/2)))
        data_y = a * np.exp(-.5 * np.float64(np.float64(x - x0) / sigma) ** 2)
        data_y = np.array(data_y) #/ np.sum(data_y))
        #data_y = np.array(data_y / np.sum(data_y))
        return data_y
    
    def bin(self, en_st, data_x, data_y):
        buf = self.delta_energy(en_st)
        delta_en = self.delta_energy(data_x)
        mat = []
        for i in range(len(buf)):
            line = self.gauss(data_x, buf[i], en_st[i])
            mat.append(line)
        self.mat = mat
        #data_st = np.matmul(np.array(mat), data_y)
        data_st = np.matmul(np.array(delta_en * mat), data_y)
        return data_st.transpose()

    def get_plot_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True):
        if len(plotting_dic) > 0:
            self.num = plotting_dic['numerator']
            self.den = plotting_dic['denominator']
            self.log = plotting_dic['log']
            division = self.num/self.den
            self.num_orig = plotting_dic['original_numerator']
            self.den_orig = plotting_dic['original_denominator']
            division = self.num/self.den
            division_orig = self.num_orig/self.den_orig
            if self.log:
                division = np.log(np.abs(division))
                division_orig = np.log(np.abs(division_orig))
            self.abs = division
            self.abs_orig = division_orig

        else:
            self.abs = np.log(self.i0_interp / self.it_interp)
            self.abs_orig = np.log(self.i0_orig / self.it_orig)
        
        #ax.plot(self.en_grid, self.abs, color)
        #ax.grid(True)
        xlabel = 'Energy (eV)'
        ylabel = 'Log(i0 / it)'

        return [self.en_grid, self.abs, color, xlabel, ylabel, ax]

    def plot(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        if len(plotting_dic) > 0:
            self.num = plotting_dic['numerator']
            self.den = plotting_dic['denominator']
            self.log = plotting_dic['log']
            division = self.num/self.den
            self.num_orig = plotting_dic['original_numerator']
            self.den_orig = plotting_dic['original_denominator']
            division = self.num/self.den
            division_orig = self.num_orig/self.den_orig
            if self.log:
                division = np.log(np.abs(division))
                division_orig = np.log(np.abs(division_orig))
            self.abs = division
            self.abs_orig = division_orig

        else:
            self.abs = np.log(self.i0_interp / self.it_interp)
            self.abs_orig = np.log(self.i0_orig / self.it_orig)
        
        ax.plot(self.en_grid, self.abs, color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('Log(i0 / it)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('Log(i0 / it)')    

    def get_plotder_info(self, plotting_dic = dict(), ax=plt, color='b'):
        if len(plotting_dic) > 0:
            num = plotting_dic['numerator']
            den = plotting_dic['denominator']
            log = plotting_dic['log']
            division = num/den
            division[division <= 0] = 1
            if log:
                division = np.log(division)
            self.abs = division

        else:
            division = self.i0_interp[:,1] / self.it_interp[:,1]
            division[division <= 0] = 1
            division = np.log(division)
            self.abs = division
            
        self.abs_der = np.diff(self.abs)
        self.abs_der = np.append(self.abs_der[0], self.abs_der)

        #ax.plot(self.en_grid, self.abs_der, color)
        #ax.grid(True)
        xlabel = 'Energy (eV)'
        ylabel = 'Log(i0 / it)'

        return [self.en_grid, self.abs_der, color, xlabel, ylabel, ax]

    def plot_der(self, plotting_dic = dict(), ax=plt, color='b'):
        if len(plotting_dic) > 0:
            num = plotting_dic['numerator']
            den = plotting_dic['denominator']
            log = plotting_dic['log']
            division = num/den
            if log:
                division = np.log(division)
            self.abs = division

        else:
            self.abs = np.log(self.i0_interp[:,1] / self.it_interp[:,1])
            
        self.abs_der = np.diff(self.abs)
        self.abs_der = np.append(self.abs_der[0], self.abs_der)

        ax.plot(self.en_grid, self.abs_der, color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('Log(i0 / it)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('Log(i0 / it)')    

    def get_derivative(self, array):
        derivative = np.diff(array)
        derivative = np.append(array[0], derivative)
        return derivative


    def export_dat(self, filename, header = ''):
        filename = filename[0: len(filename) - 3] + 'dat'
        np.savetxt(filename, np.array([self.en_grid, self.i0_interp, self.it_interp, self.ir_interp, self.iff_interp]).transpose(), fmt='%.7e %15.7e %15.7e %15.7e %15.7e', comments = '', header = header)
        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename])

    def export_dat_gen(self, filename):
        comments = XASdataGeneric.read_header(None, filename)
        comments = comments[0: comments.rfind('#')] + '# '

        filename = filename[0: len(filename) - 3] + 'dat'

        copy_interp = collections.OrderedDict(sorted(self.binned_arrays.items())).copy()
        #copy_interp = self.binned_arrays.copy()
        if '1' in copy_interp:
            del copy_interp['1']
        keys = copy_interp.keys()
        matrix = []

        energy_header = ''
        if 'energy' in copy_interp.keys():
            matrix.append(copy_interp['energy'])
            del copy_interp['energy']
            energy_header = 'energy'
        elif 'En. (eV)' in copy_interp.keys():
            matrix.append(copy_interp['En. (eV)'])
            del copy_interp['En. (eV)']
            energy_header = 'En. (eV)'

        i0_header = ''
        if 'i0' in copy_interp.keys():
            matrix.append(copy_interp['i0'])
            del copy_interp['i0']
            i0_header = 'i0'
        elif 'i0 (V)' in copy_interp.keys():
            matrix.append(copy_interp['i0 (V)'])
            del copy_interp['i0 (V)']
            i0_header = 'i0 (V)'

        it_header = ''
        if 'it' in copy_interp.keys():
            matrix.append(copy_interp['it'])
            del copy_interp['it']
            it_header = 'it'
        elif 'it(V)' in copy_interp.keys():
            matrix.append(copy_interp['it(V)'])
            del copy_interp['it(V)']
            it_header = 'it(V)'

        ir_header = ''
        if 'ir' in copy_interp.keys():
            matrix.append(copy_interp['ir'])
            del copy_interp['ir']
            ir_header = 'ir'
        elif 'ir(V)' in copy_interp.keys():
            matrix.append(copy_interp['ir(V)'])
            del copy_interp['ir(V)']
            ir_header = 'ir(V)'

        iff_header = ''
        if 'iff' in copy_interp.keys():
            matrix.append(copy_interp['iff'])
            del copy_interp['iff']
            iff_header = 'iff'
        elif 'iff(V)' in copy_interp.keys():
            matrix.append(copy_interp['iff(V)'])
            del copy_interp['iff(V)']
            iff_header = 'iff(V)'


        for key in copy_interp.keys():
            matrix.append(copy_interp[key])
        matrix = np.array(matrix).transpose()

        fmt = ' '.join(['%12.6f' for key in copy_interp.keys()])
        header = '  '.join(copy_interp.keys())

        if iff_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(iff_header, header)
        if ir_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(ir_header, header)
        if it_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(it_header, header)
        if i0_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(i0_header, header)
        if energy_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(energy_header, header)

        np.savetxt(filename,
                   matrix,
                   fmt=fmt,
                   delimiter=" ",
                   header = header,
                   comments = comments)
        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename])
        return filename




        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename])


    def plot_orig(self, ax=plt, color='r'):
        ax.plot(self.sorted_matrix[:, 1], np.log(self.sorted_matrix[:, 2]/self.sorted_matrix[:, 3]), color)
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('(iflu / i0)')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('(iflu / i0)')    


    def process(self, timestamp, energy, i0, it, ir, iff, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):
        self.ts_orig = timestamp
        self.en_orig = energy
        self.i0_orig = i0
        self.it_orig = it
        self.ir_orig = ir
        self.iff_orig = iff

        self.matrix = np.array([timestamp, energy, i0, it, ir, iff]).transpose()  
        self.sorted_matrix = self.sort_data(self.matrix, 1)
        self.en_grid = self.energy_grid(self.sorted_matrix[:, 1], e0, edge_start, edge_end, preedge_spacing, xanes, exafsk)
        self.data_en, self.data_i0, self.data_it, self.data_ir, self.data_iff = self.average_points(self.sorted_matrix[:, 1], self.sorted_matrix[:, 2], self.sorted_matrix[:, 3], self.sorted_matrix[:, 4], self.sorted_matrix[:, 5])
        self.i0_interp = self.bin(self.en_grid, self.data_en, self.data_i0)
        self.it_interp = self.bin(self.en_grid, self.data_en, self.data_it)
        self.ir_interp = self.bin(self.en_grid, self.data_en, self.data_ir)
        self.iff_interp = self.bin(self.en_grid, self.data_en, self.data_iff)
        self.abs = np.log(self.i0_interp/self.it_interp)

        self.abs_der = np.diff(self.abs)
        self.abs_der = np.append(self.abs_der[0], self.abs_der)


    def process_gen(self, interp_dict, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk, energy_string = 'energy'):

        self.matrix = interp_dict[energy_string][:, 1]

        self.matrix = np.vstack((self.matrix, np.array([interp_dict[array][:, 1] for array in list(interp_dict.keys()) if array != energy_string]))).transpose()
        self.sorted_matrix = self.sort_data(self.matrix, 0)
        self.en_grid = self.energy_grid(self.sorted_matrix[:, 0], e0, edge_start, edge_end, preedge_spacing, xanes, exafsk)

        self.data_matrix = self.average_points_gen(self.sorted_matrix, 0)
        self.data_arrays = {energy_string: self.data_matrix[:, 0]}

        keys = [array for array in list(interp_dict.keys()) if array != energy_string]
        for i in range(len(keys)):
            self.data_arrays[keys[i]] = self.data_matrix[:, i + 1]

        self.binned_arrays = {energy_string: self.en_grid}
        for i in range(len(keys) + 1):
            if list(self.data_arrays.keys())[i] != energy_string:
                self.binned_arrays[list(self.data_arrays.keys())[i]] = self.bin(self.en_grid, self.data_arrays[energy_string], self.data_arrays[list(self.data_arrays.keys())[i]])

        return self.binned_arrays

    def process_equal(self, timestamp, energy, i0, it, ir, iff, delta_en = 2):
        self.ts_orig = timestamp
        self.en_orig = energy
        self.i0_orig = i0
        self.it_orig = it
        self.ir_orig = ir
        self.iff_orig = iff

        self.matrix = np.array([timestamp, energy, i0, it, ir, iff]).transpose()  
        self.sorted_matrix = self.sort_data(self.matrix, 1)
        self.en_grid = self.energy_grid_equal(self.sorted_matrix[:, 1], delta_en)
        self.data_en, self.data_i0, self.data_it, self.data_ir, self.data_iff = self.average_points(self.sorted_matrix[:, 1], self.sorted_matrix[:, 2], self.sorted_matrix[:, 3], self.sorted_matrix[:, 4], self.sorted_matrix[:, 5])
        self.i0_interp = self.bin(self.en_grid, self.data_en, self.data_i0)
        self.it_interp = self.bin(self.en_grid, self.data_en, self.data_it)
        self.ir_interp = self.bin(self.en_grid, self.data_en, self.data_ir)
        self.iff_interp = self.bin(self.en_grid, self.data_en, self.data_iff)
        self.abs = np.log(self.i0_interp/self.it_interp)

        self.abs_der = np.diff(self.abs)
        self.abs_der = np.append(self.abs_der[0], self.abs_der)

        self.abs_der2 = np.diff(self.abs_der)
        self.abs_der2 = np.append(self.abs_der2[0], self.abs_der2)

    def process_equal_gen(self, interp_dict, energy_string = 'energy', delta_en = 2):
        self.matrix = interp_dict[energy_string][:, 1]

        self.matrix = np.vstack((self.matrix, np.array([interp_dict[array][:, 1] for array in list(interp_dict.keys()) if array != energy_string]))).transpose()
        self.sorted_matrix = self.sort_data(self.matrix, 0)
        self.en_grid = self.energy_grid_equal(self.sorted_matrix[:, 0], delta_en)

        self.data_matrix = self.average_points_gen(self.sorted_matrix, 0)
        self.data_arrays = {energy_string: self.data_matrix[:, 0]}
        keys = [array for array in list(interp_dict.keys()) if array != energy_string]
        for i in range(len(keys)):
            self.data_arrays[keys[i]] = self.data_matrix[:, i + 1]

        self.binned_eq_arrays = {energy_string: self.en_grid}
        for i in range(len(keys) + 1):
            if list(self.data_arrays.keys())[i] != energy_string:
                self.binned_eq_arrays[list(self.data_arrays.keys())[i]] = self.bin(self.en_grid, self.data_arrays[energy_string], self.data_arrays[list(self.data_arrays.keys())[i]])

        return self.binned_eq_arrays

    def average_points(self, energy, i0, it, ir, iff):
        i = 0
        listenergy = []
        listi0 = []
        listit = []
        listir = []
        listiff = []
        while i < len(energy):
            condition = (energy[i] == energy)
            energy_interval = np.extract(condition, energy)
            #print(energy_interval)
            energy_index = np.where(energy == energy_interval[0])[0]
            #print(energy_interval)
            i = energy_index[len(energy_index) - 1] + 1
            #print(i)
            listenergy.append(np.mean(energy_interval))
            listi0.append(np.mean(np.extract(condition, i0)))
            listit.append(np.mean(np.extract(condition, it)))
            listir.append(np.mean(np.extract(condition, ir)))
            listiff.append(np.mean(np.extract(condition, iff)))
        return np.array(listenergy), np.array(listi0), np.array(listit), np.array(listir), np.array(listiff)

    def average_points_gen(self, matrix, energy_column = 0):
        i = 0
        listenergy = []
        indexes = list(range(len(matrix[0])))
        indexes.remove(energy_column)
        lists = [list() for i in range(len(indexes))]

        energy = matrix[:,0]
        diff = np.diff(matrix[:,0])
        diff_indexes = np.where(diff==0)[0]
        diff2 = np.diff(diff_indexes)

        import time
        while len(diff[diff==0]) > 0:
            diff_index = np.where(diff==0)[0]
            last_i = diff_index[len(diff_index) - 1] + 2
            for i in diff_index[::-1]:
                if i < last_i - 1:
                    energy = matrix[:,0]
                    condition = (energy[i] == energy)
                    energy_interval = np.extract(condition, energy)
                    energy_index = np.where(energy == energy_interval[0])[0]
                    for j in range(len(matrix[0])):
                        matrix[i, j] = np.mean(np.extract(condition, matrix[:,j]))
                    matrix = np.delete(matrix, energy_index[1:], 0)
                last_i = i
            diff = np.diff(matrix[:,0])
        
        return matrix


    def get_edge_index(self, abs):
        abs_der = np.diff(abs)
        abs_der = np.append(abs_der[0], abs_der)

        abs_der2 = np.diff(abs_der)
        abs_der2 = np.append(abs_der2[0], abs_der2)

        abs_der[0:int(len(abs_der) * 0.005)] = 0
        abs_der2[0:int(np.round(len(abs_der2) * 0.005))] = 0
        for i in range(len(abs_der)):
            # Get der max
            max_index_der = np.where(max(np.abs(abs_der)) == np.abs(abs_der))[0][0]
        
            # Get der2 max
            max_index_der2 = np.where(max(abs_der2) == abs_der2)[0][0]
        
            # Get der2 min
            min_index_der2 = np.where(min(abs_der2) == abs_der2)[0][0]
        
            if max_index_der >= min([min_index_der2, max_index_der2]) and max_index_der <= max([min_index_der2, max_index_der2]):
                print('Found the edge! (I think...)')
                return max_index_der - 1
        
            else:
                print('Still looking for the edge...')
                abs_der[min([min_index_der2, max_index_der2]) : max([min_index_der2, max_index_der2]) + 1] = 0
                abs_der2[min([min_index_der2, max_index_der2]) : max([min_index_der2, max_index_der2]) + 1] = 0

        return -1
