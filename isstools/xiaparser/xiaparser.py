from netCDF4 import Dataset
from optparse import OptionParser
import matplotlib.pyplot as plt
import sys
import ctypes
import numpy as np
import os
import os.path
from scipy.optimize import curve_fit
import smbc
import time as ttime


'''
# Information of file format on: http://www.xia.com/Manuals/XMAP_User_Manual.pdf / Section 5.3.3.2 Buffer Header
File Structure:

- Buffer Header
- Pixel X Data Block
- Pixel X+1 Data Block
- Pixel X+2 Data Block
...
'''

class xiaparser:
    def __init__(self, **kwargs):
        self.filename = ''
        self.filepath = ''
        self.exporting_arrays = []
        self.chan0 = []
        self.chan1 = []
        self.chan2 = []
        self.chan3 = []
        self.next_pos = 0


    def parse(self, filename, filepath, silent = True, printheaders = False, plotdata = False, pixelnumber = None):

        self.filename = ''
        self.filepath = ''
        self.exporting_arrays = []
        self.next_pos = 0

        if(filename != self.filename or filepath != self.filepath or pixelnumber != None):
            self.filename = filename
            self.filepath = filepath
            self.rootgrp = Dataset(filepath + filename, "r")
            self.data = self.rootgrp.variables["array_data"][:]

            if not silent:
                print("-"*80)
                print("File name:", filepath + filename)
                print("-"*80)
                print("Total Data Shape:", self.data.shape)
                if (pixelnumber != None):
                    print("Printing pixel:", pixelnumber)
                print("-"*80)

            for ds_index, ds in enumerate(self.data):
                #ds = ds[0]
                #self.chan0 = []
                #self.chan1 = []
                #self.chan2 = []
                #self.chan3 = []
                for board_number, curr_ds in enumerate(ds):
                    if(ds_index == 0):
                        self.exporting_arrays.append([])
                        self.exporting_arrays.append([])
                        self.exporting_arrays.append([])
                        self.exporting_arrays.append([])
                    self.chans = [[] for _ in range(4)]
                    if(printheaders and not silent):
                        print("-"*80)
                        print("Dataset Shape: ", curr_ds.shape)
                        print("-"*80)
                        print("Header")
                        print("-"*80)
                    self.next_pos = 256
                    number_pixels = self.read_header(curr_ds, printheaders, silent)
                    for i in range(number_pixels):
                        self.next_pos = self.read_pixel_block(curr_ds, board_number, i, self.next_pos, plotdata, pixelnumber, silent)
                    for index, channel in enumerate([channel_num + board_number * 4 for channel_num in range(4)]):
                        self.exporting_arrays[channel] = self.exporting_arrays[channel] + self.chans[index]
                    #self.exporting_arrays.append(self.chan0)
                    #self.exporting_arrays.append(self.chan1)
                    #self.exporting_arrays.append(self.chan2)
                    #self.exporting_arrays.append(self.chan3)

    def export_files(self, dest_filepath, dest_filename = '', all_in_one = True):

        if dest_filename == '':
            tmpfilename = self.filename[0:len(self.filename)-3]
        else:
            tmpfilename = dest_filename

        try_number = 2

        while(os.path.isfile(dest_filepath + tmpfilename)):
            tmpfilename = self.filename[0:len(self.filename)-3] + '-' + str(try_number)
            try_number += 1

        if all_in_one:
            print("Creating file for all channels...")
            output_data = np.array([array for array in self.exporting_arrays])
            with open(dest_filepath + tmpfilename + '-allchans.txt', 'wb') as f:
                i = 0
                for row in output_data:
                    print('Channel number: {}'.format(i))
                    i += 1
                    np.savetxt(f, np.array(row), fmt='%i',delimiter=' ', footer='============================================================')
                

        else:
            for index, array in enumerate(exporting_arrays):
                print('Creating file for channel {}...'.format(index))
                np.savetxt('{}{}-chan{}.txt'.format(dest_filepath, tmpfilename, index), array, fmt='%i', delimiter=' ')
      
        
    def read_pixel_block(self, dataset, board_number, pixel, start_pos, plot_data, pixel_to_parse, silent):
        def read_statistics(ds, start):
            pos = start
            #print("Realtime Low:", ds[pos])
            #print("Realtime High:", ds[pos+1])
            realtime = self.two_word_to_int(ds[pos], ds[pos+1])*320/1000000  # 320ns
            pos += 2
            livetime = self.two_word_to_int(ds[pos], ds[pos+1])*320/1000000  # 320ns
            pos += 2
            triggers = self.two_word_to_int(ds[pos], ds[pos+1])
            pos += 2
            output_events = self.two_word_to_int(ds[pos], ds[pos+1])
            return realtime, livetime, triggers, output_events
    
        pos = start_pos #256 + (pixel + 1) *  #(pixel+1)*256
        tag_word_0 = dataset[pos+0]  # Tag Word 0: 0x33CC
        tag_word_1 = dataset[pos+1]  # Tag Word 0: 0xCC33
        pixel_header_size = dataset[pos+2]
        mapping_mode = dataset[pos+3]  # 1 = Full Spectrum, 2 = Multiple ROI, 3 = List Mode
        pixel_number = self.two_word_to_int(dataset[pos+4], dataset[pos+5])
        total_pixel_block_size = self.two_word_to_int(dataset[pos+6], dataset[pos+7])
        
        self.next_pos = start_pos + total_pixel_block_size
    
        K = channel_0_size = dataset[pos+8]  # Channel 0 Size (K words)
        L = channel_1_size = dataset[pos+9]  # Channel 1 Size (L words)
        M = channel_2_size = dataset[pos+10]  # Channel 2 Size (M words)
        N = channel_3_size = dataset[pos+11]  # Channel 3 Size (N words)
        
        reserved = dataset[pos+12:31]  # reserved (set to 0)
        
        channel_0_stats_realtime, channel_0_stats_livetime, channel_0_stats_triggers, channel_0_stats_output_evs = read_statistics(dataset, pos+32)
        channel_1_stats_realtime, channel_1_stats_livetime, channel_1_stats_triggers, channel_1_stats_output_evs = read_statistics(dataset, pos+40)
        channel_2_stats_realtime, channel_2_stats_livetime, channel_2_stats_triggers, channel_2_stats_output_evs = read_statistics(dataset, pos+48)
        channel_3_stats_realtime, channel_3_stats_livetime, channel_3_stats_triggers, channel_3_stats_output_evs = read_statistics(dataset, pos+56)
        
        reserved = dataset[pos+64:256]#255]  # reserved (set to 0)
        
        channel_0_spectrum = dataset[pos+256:pos+256+K-1+1] # Python gets range - 1
        channel_1_spectrum = dataset[pos+256+K:pos+256+K+L-1+1]
        channel_2_spectrum = dataset[pos+256+K+L:pos+256+K+L+M-1+1]
        channel_3_spectrum = dataset[pos+256+K+L+M:pos+256+K+L+M+N-1+1]    

        self.chans[0].append(channel_0_spectrum)
        self.chans[1].append(channel_1_spectrum)
        self.chans[2].append(channel_2_spectrum)
        self.chans[3].append(channel_3_spectrum)
    
        number = 0
        if pixel_to_parse is not None:
            number = np.uint64((pixel_to_parse + 1) or -1) - 1
        if ((pixel_number == number or pixel_to_parse == None) and (not silent)):
            print("-"*40)
            print("Pixel Number:", pixel_number, "\n")
            print("Tag Word 0:", format(tag_word_0 & 0xffff, '#06x'))
            print("Tag Word 1:", format(tag_word_1 & 0xffff, '#06x'))
            print("Pixel Header Size:", pixel_header_size)
            print("Mapping Mode:", mapping_mode)
            #print("Pixel Number:", pixel_number)
            print("Total Pixel Block Size:", total_pixel_block_size, "\n")
        
            print("Channel {} Size: {}".format((4 * board_number) + 0, channel_0_size))
            print("Channel {} Realtime: {} ms".format((4 * board_number) + 0, channel_0_stats_realtime))
            print("Channel {} Livetime: {} ms".format((4 * board_number) + 0, channel_0_stats_livetime))
            print("Channel {} Triggers: {}".format((4 * board_number) + 0, channel_0_stats_triggers & 0xffff))
            print("Channel {} Output Events: {}".format((4 * board_number) + 0, channel_0_stats_output_evs & 0xffff))
            print("Channel {} Spectrum: {}\n".format((4 * board_number) + 0, channel_0_spectrum))
        
            print("Channel {} Size: {}".format((4 * board_number) + 1, channel_1_size))
            print("Channel {} Realtime: {} ms".format((4 * board_number) + 1, channel_1_stats_realtime))
            print("Channel {} Livetime: {} ms".format((4 * board_number) + 1, channel_1_stats_livetime))
            print("Channel {} Triggers: {}".format((4 * board_number) + 1, channel_1_stats_triggers & 0xffff))
            print("Channel {} Output Events: {}".format((4 * board_number) + 1, channel_1_stats_output_evs & 0xffff))
            print("Channel {} Spectrum: {}\n".format((4 * board_number) + 1, channel_1_spectrum))
        
            print("Channel {} Size: {}".format((4 * board_number) + 2, channel_2_size))
            print("Channel {} Realtime: {} ms".format((4 * board_number) + 2, channel_2_stats_realtime))
            print("Channel {} Livetime: {} ms".format((4 * board_number) + 2, channel_2_stats_livetime))
            print("Channel {} Triggers: {}".format((4 * board_number) + 2, channel_2_stats_triggers & 0xffff))
            print("Channel {} Output Events: {}".format((4 * board_number) + 2, channel_2_stats_output_evs & 0xffff))
            print("Channel {} Spectrum: {}\n".format((4 * board_number) + 2, channel_2_spectrum))
        
            print("Channel {} Size: {}".format((4 * board_number) + 3, channel_3_size))
            print("Channel {} Realtime: {} ms".format((4 * board_number) + 3, channel_3_stats_realtime))
            print("Channel {} Livetime: {} ms".format((4 * board_number) + 3, channel_3_stats_livetime))
            print("Channel {} Triggers: {}".format((4 * board_number) + 3, channel_3_stats_triggers & 0xffff))
            print("Channel {} Output Events: {}".format((4 * board_number) + 3, channel_3_stats_output_evs & 0xffff))
            print("Channel {} Spectrum: {}".format((4 * board_number) + 3, channel_3_spectrum))
        
            if plot_data:# and len(channel_0_spectrum):
                print('plotting?')
                fig = plt.figure()
                fig.suptitle("Pixel #"+str(pixel_number))
                ax = fig.gca()
                ax.plot(channel_0_spectrum, label="Channel {} / RT: {} / LT: {}".format((4 * board_number) + 0, channel_0_stats_realtime, channel_0_stats_livetime))
                ax.plot(channel_1_spectrum, label="Channel {} / RT: {} / LT: {}".format((4 * board_number) + 1, channel_1_stats_realtime, channel_1_stats_livetime))
                ax.plot(channel_2_spectrum, label="Channel {} / RT: {} / LT: {}".format((4 * board_number) + 2, channel_2_stats_realtime, channel_2_stats_livetime))
                ax.plot(channel_3_spectrum, label="Channel {} / RT: {} / LT: {}".format((4 * board_number) + 3, channel_3_stats_realtime, channel_3_stats_livetime))
                plt.legend(loc="best")
                plt.show()
        
        return self.next_pos


    def two_word_to_int(self, wlow, whigh):
        number = ((whigh & 0xFFFF) << 16) + (wlow & 0xFFFF) 
        return number
    

    def read_header(self, dataset, print_headers, silent):
        tag_word_0 = dataset[0]  # Tag Word 0: 0x55AA
        tag_word_1 = dataset[1]  # Tag Word 0: 0xAA55
        buffer_header_size = dataset[2]  # Buffer Header Size (=256)
        mapping_mode = dataset[3]  # 1 = Full Spectrum, 2 = Multiple ROI, 3 = List Mode
        run_number = dataset[4]  # Run Number
        seq_buffer_number = self.two_word_to_int(dataset[5], dataset[6])  # Seq Buffer Number (low word first)
        buffer_id = dataset[7]  # BufferID (0: A, 1:B)
        number_of_pixels_in_buffer = dataset[8]  # Number of Pixels in buffer
    
        starting_pixel_number = self.two_word_to_int(dataset[9], dataset[10])  # Starting Pixel Number (low word first)
        module_serial_number = dataset[11]  # Module Serial Number?/Module #
    
        detector_channel_0 = dataset[12]  # Detector Channel 0 (set by host in DSP)
        detector_elem_channel_0 = dataset[13]  # Det. Element, Ch0
        detector_channel_1 = dataset[14]  # Detector Channel 1 (set by host in DSP)
        detector_elem_channel_1 = dataset[15]  # Det. Element, Ch1
        detector_channel_2 = dataset[16]  # Detector Channel 2 (set by host in DSP)
        detector_elem_channel_2 = dataset[17]  # Det. Element, Ch2
        detector_channel_3 = dataset[18]  # Detector Channel 3 (set by host in DSP)
        detector_elem_channel_3 = dataset[19]  # Det. Element, Ch3
    
        channel_0_size = dataset[20]  #Channel 0 Size (number of words)
        channel_1_size = dataset[21]  #Channel 1 Size (number of words)
        channel_2_size = dataset[22]  #Channel 2 Size (number of words)
        channel_3_size = dataset[23]  #Channel 3 Size (number of words)
    
        buffer_errors = dataset[24]  # Buffer errors: Buffer overrun 0: No error / >0: Number of extra pixels combined with last pixel in buffer
        reserved = dataset[25:32]#31]  # Reserved (set to 0)
        user_words = dataset[32:64]#63]  # 32 User words (set in USER DSP array)
        reserved = dataset[64:256]#255]  # Reserved (set to 0)
    
        if(print_headers and not silent):
            print("Tag Word 0:", format(tag_word_0 & 0xffff, '#06x')) #tag_work_0)
            print("Tag Word 1:", format(tag_word_1 & 0xffff, '#06x')) #tag_word_1)
            print("Buffer Header Size:", buffer_header_size)
            print("Mapping Mode:", mapping_mode)
            print("Run Number:", run_number)
            print("Sequential Buffer Number:", seq_buffer_number)
            print("Buffer ID:", buffer_id)
            print("Number of Pixels in Buffer:", number_of_pixels_in_buffer)
            print("Starting Pixel Number:", starting_pixel_number)
            print("Module Serial Number:", module_serial_number)
            print("Detector Channel 0:", detector_channel_0)
            print("Detector Element Ch 0:", detector_elem_channel_0)
            print("Detector Channel 1:", detector_channel_1)
            print("Detector Element Ch 1:", detector_elem_channel_1)
            print("Detector Channel 2:", detector_channel_2)
            print("Detector Element Ch 2:", detector_elem_channel_2)
            print("Detector Channel 3:", detector_channel_3)
            print("Detector Element Ch 3:", detector_elem_channel_3)
            print("Channel 0 Size:", channel_0_size)
            print("Channel 1 Size:", channel_1_size)
            print("Channel 2 Size:", channel_2_size)
            print("Channel 3 Size:", channel_3_size)
            print("Buffer Errors:", buffer_errors)
            print("User Words:", user_words)
    
        return number_of_pixels_in_buffer


    def channelsCount(self):
        return len(self.exporting_arrays)

    def pixelsCount(self, channel):
        if channel < self.channelsCount():
            return len(self.exporting_arrays[channel])
        raise Exception("There is no channel {}".format(channel))


    def parse_roi(self, pixels, channel_number, min_energy = 0, max_energy = 20):
        energies = []
        integs = []
        for i in frange(0, 20, 20/2047):
            energies.append(i)
        curr_pixel = self.exporting_arrays[channel_number - 1]#getattr(self, "exporting_array" + "{}".format(channel_number))
        for i in pixels:
            condition = (np.array(energies) <= max_energy) == (np.array(energies) >= min_energy)
            interval = np.extract(condition, curr_pixel[i][:])
            integ = sum(interval)
            integs.append(integ)
        return np.array(integs)



    def plot_roi(self, filename, filepath, pixels, channel_number, min_energy = 0, max_energy = 20, ax = plt, energy_array = np.array([]), background = []):

        self.parse(filename, filepath)
        parsed_roi_array = self.parse_roi(pixels, channel_number, min_energy, max_energy)
        if len(background) == len(parsed_roi_array):
            parsed_roi_array = -(parsed_roi_array / background)

        if(len(energy_array) == len(parsed_roi_array)):
            ax.plot(energy_array[:, 1], parsed_roi_array)
        else:
            ax.plot(parsed_roi_array)
            if(len(energy_array)):
                print('The parsed ROI array and the energy array have different lengths.. \nPlotting only parsed_roi_array\nenergy_array length: {}\nparsed_roi_array length: {}'.format(len(energy_array), len(parsed_roi_array)))
        ax.grid(True)

        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (eV)')
            ax.ylabel('Intensity')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (eV)')
            ax.set_ylabel('Intensity')



    def gauss(self, x, *p):
        A, mu, sigma = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2))


    def gain_matching(self, xia, center_energy, scan_range, channel_number, ax=plt):
    
        center_energy = float(center_energy)
        scan_range = float(scan_range)

        graph_x = xia.mca_x.value
        graph_data = getattr(xia, "mca_array" + "{}".format(channel_number) + ".value")
    
        condition = (graph_x <= (center_energy + scan_range)/1000) == (graph_x > (center_energy - scan_range)/1000)
        interval_x = np.extract(condition, graph_x)
        interval = np.extract(condition, graph_data)

        # p0 is the initial guess for fitting coefficients (A, mu and sigma)
        p0 = [.1, center_energy/1000, .1]
        coeff, var_matrix = curve_fit(self.gauss, interval_x, interval, p0=p0) 
        print('Intensity = ', coeff[0])
        print('Fitted mean = ', coeff[1])
        print('Sigma = ', coeff[2])

        # For testing (following two lines)
        ax.plot(interval_x, interval, 'b')
        ax.plot(interval_x, self.gauss(interval_x, *coeff), 'r')
        ax.grid(True)
        if 'xlabel' in dir(ax):
            ax.xlabel('Energy (keV)')
            ax.ylabel('Intensity')
        elif 'set_xlabel' in dir(ax):
            ax.set_xlabel('Energy (keV)')
            ax.set_ylabel('Intensity')

        return coeff
        
    def parse_step_scan(set_name, roi_start, roi_end, path = '/GPFS/xf08id/xia_files/'):
        det_channels = []

        energies, i0_values = np.loadtxt("{}{}-{}".format(path, set_name, "i0")).transpose()
        det_channels.append(energies)
        det_channels.append(i0_values - pba1.adc7.offset.value)

        for i in range(4):
            cur_det = np.loadtxt("{}{}-{}".format(path, set_name, i + 1))
            cur_det_roi = [];
            for i in cur_det:
                cur_det_roi.append(np.sum(i[roi_start:roi_end + 1]))
            det_channels.append(cur_det_roi)

        det_channels.append(np.array(det_channels[2]) + np.array(det_channels[3]) + np.array(det_channels[4]) + np.array(det_channels[5]))
        det_channels = np.array(det_channels).transpose()
        np.savetxt("{}{}-parsed.txt".format(path, set_name), det_channels)
        return np.array(det_channels)


def frange(start, stop, step):
    i = start
    while i < stop:
        yield i
        i += step

class smbclient:
    def __init__(self, filename = '', dest_filename = '', **kwargs):
        self.ctx = smbc.Context()
        self.ctx.optionNoAutoAnonymousLogin = True
        self.ctx.functionAuthData = self.auth_fn
        self.filename = filename # 'smb://elistavitski-ni/epics/elis_xia11_024.nc'
        self.dest_filename = dest_filename

    # Load different filenames (in case no filename was passed before)
    def load(self, filename, dest_filename):
        self.filename = filename
        self.dest_filename = dest_filename

    # Copy source file to dest file
    def copy(self):
        source_file = self.ctx.open(self.filename, os.O_RDONLY)
        dest_file = open(self.dest_filename, 'wb')
        dest_file.write(source_file.read())
        dest_file.flush()
        source_file.close()
        dest_file.close()

    def auth_fn(self, server, share, workgroup, username, password):
        return ('elistavitski-ni', 'Eli Stavitski', 'issuser')









