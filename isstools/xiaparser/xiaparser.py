from netCDF4 import Dataset
from optparse import OptionParser
import matplotlib.pyplot as plt
import sys
import ctypes
import numpy as np
import os.path


'''
# Information of file format on: http://www.xia.com/Manuals/XMAP_User_Manual.pdf / Section 5.3.3.2 Buffer Header
File Structure:

- Buffer Header
- Pixel X Data Block
- Pixel X+1 Data Block
- Pixel X+2 Data Block
...
'''

#get_bin = lambda x, n: format(x, 'b').zfill(n)
get_bin = lambda x, n: bin(x)[2:].zfill(n)
global next_pos
exporting_array1 = []
exporting_array2 = []
exporting_array3 = []
exporting_array4 = []

class Nop(object):
    def nop(*args, **kw): pass

    def __getattr__(self, _): return self.nop

def int32_to_uint32(i):
    return ctypes.c_uint32(i).value

def two_word_to_int(wlow, whigh):
    #print("Low: ", wlow)
    #print("High:", whigh)
    number = ((whigh & 0xFFFF) << 16) + (wlow & 0xFFFF) #int(get_bin(whigh,16)+get_bin(wlow,16))
    #number = int(get_bin(int32_to_uint32(whigh), 16)+get_bin(int32_to_uint32(wlow), 16),2)
    return number

def read_header(dataset, print_headers):
    tag_word_0 = dataset[0]  # Tag Word 0: 0x55AA
    tag_word_1 = dataset[1]  # Tag Word 0: 0xAA55
    buffer_header_size = dataset[2]  # Buffer Header Size (=256)
    mapping_mode = dataset[3]  # 1 = Full Spectrum, 2 = Multiple ROI, 3 = List Mode
    run_number = dataset[4]  # Run Number
    seq_buffer_number = two_word_to_int(dataset[5], dataset[6])  # Seq Buffer Number (low word first)
    buffer_id = dataset[7]  # BufferID (0: A, 1:B)
    number_of_pixels_in_buffer = dataset[8]  # Number of Pixels in buffer

    starting_pixel_number = two_word_to_int(dataset[9], dataset[10])  # Starting Pixel Number (low word first)
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

    if(print_headers):
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

def read_pixel_block(dataset, pixel, start_pos, plot_data, pixel_to_parse):
    def read_statistics(ds, start):
        pos = start
        #print("Realtime Low:", ds[pos])
        #print("Realtime High:", ds[pos+1])
        realtime = two_word_to_int(ds[pos], ds[pos+1])*320/1000000  # 320ns
        pos += 2
        livetime = two_word_to_int(ds[pos], ds[pos+1])*320/1000000  # 320ns
        pos += 2
        triggers = two_word_to_int(ds[pos], ds[pos+1])
        pos += 2
        output_events = two_word_to_int(ds[pos], ds[pos+1])
        return realtime, livetime, triggers, output_events

    pos = start_pos #256 + (pixel + 1) *  #(pixel+1)*256
    tag_word_0 = dataset[pos+0]  # Tag Word 0: 0x33CC
    tag_word_1 = dataset[pos+1]  # Tag Word 0: 0xCC33
    pixel_header_size = dataset[pos+2]
    mapping_mode = dataset[pos+3]  # 1 = Full Spectrum, 2 = Multiple ROI, 3 = List Mode
    pixel_number = two_word_to_int(dataset[pos+4], dataset[pos+5])
    total_pixel_block_size = two_word_to_int(dataset[pos+6], dataset[pos+7])
    
    next_pos = start_pos + total_pixel_block_size

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

    exporting_array1.append(channel_0_spectrum)
    exporting_array2.append(channel_1_spectrum)
    exporting_array3.append(channel_2_spectrum)
    exporting_array4.append(channel_3_spectrum)

    #print(pixel_number, pixel_to_parse, type(pixel_number), type(pixel_to_parse))
    if (pixel_number == np.uint64(pixel_to_parse or -1) or pixel_to_parse == None):
        print("-"*40)
        print("Pixel Number:", pixel_number, "\n")
        print("Tag Word 0:", format(tag_word_0 & 0xffff, '#06x'))
        print("Tag Word 1:", format(tag_word_1 & 0xffff, '#06x'))
        print("Pixel Header Size:", pixel_header_size)
        print("Mapping Mode:", mapping_mode)
        #print("Pixel Number:", pixel_number)
        print("Total Pixel Block Size:", total_pixel_block_size, "\n")
    
        print("Channel 0 Size:", channel_0_size)
        print("Channel 0 Realtime:", channel_0_stats_realtime, "ms")
        print("Channel 0 Livetime:", channel_0_stats_livetime, "ms")
        print("Channel 0 Triggers:", channel_0_stats_triggers & 0xffff)
        print("Channel 0 Output Events:", channel_0_stats_output_evs & 0xffff)
        print("Channel 0 Spectrum: ", channel_0_spectrum, "\n")
    
        print("Channel 1 Size:", channel_1_size)
        print("Channel 1 Realtime:", channel_1_stats_realtime, "ms")
        print("Channel 1 Livetime:", channel_1_stats_livetime, "ms")
        print("Channel 1 Triggers:", channel_1_stats_triggers & 0xffff)
        print("Channel 1 Output Events:", channel_1_stats_output_evs & 0xffff)
        print("Channel 1 Spectrum: ", channel_1_spectrum, "\n")
    
        print("Channel 2 Size:", channel_2_size)
        print("Channel 2 Realtime:", channel_2_stats_realtime, "ms")
        print("Channel 2 Livetime:", channel_2_stats_livetime, "ms")
        print("Channel 2 Triggers:", channel_2_stats_triggers & 0xffff)
        print("Channel 2 Output Events:", channel_2_stats_output_evs & 0xffff)
        print("Channel 2 Spectrum: ", channel_2_spectrum, "\n")
    
        print("Channel 3 Size:", channel_3_size)
        print("Channel 3 Realtime:", channel_3_stats_realtime, "ms")
        print("Channel 3 Livetime:", channel_3_stats_livetime, "ms")
        print("Channel 3 Triggers:", channel_3_stats_triggers & 0xffff)
        print("Channel 3 Output Events:", channel_3_stats_output_evs & 0xffff)
        print("Channel 3 Spectrum: ", channel_3_spectrum)
    
        if plot_data:# and len(channel_0_spectrum):
            fig = plt.figure()
            fig.suptitle("Pixel #"+str(pixel_number))
            ax = fig.gca()
            ax.plot(channel_0_spectrum, label="Channel 0 / RT: "+str(channel_0_stats_realtime)+" / LT: "+str(channel_0_stats_livetime))
            ax.plot(channel_1_spectrum, label="Channel 1 / RT: "+str(channel_1_stats_realtime)+" / LT: "+str(channel_1_stats_livetime))
            ax.plot(channel_2_spectrum, label="Channel 2 / RT: "+str(channel_2_stats_realtime)+" / LT: "+str(channel_2_stats_livetime))
            ax.plot(channel_3_spectrum, label="Channel 3 / RT: "+str(channel_3_stats_realtime)+" / LT: "+str(channel_3_stats_livetime))
            plt.legend(loc="best")
            plt.show()
    
    return next_pos


def main(filename):
    #usage = "usage: %prog [options] arg"
    #parser = OptionParser(usage)
    #parser.add_option("-f", "--file", dest="filename",
    #                  help="read data from FILENAME")
    #parser.add_option("-q", "--quiet",
    #                  action="store_true", dest="quiet")
    #parser.add_option("-p", "--plot", action="store_true",
    #                  help="plot each pixel", dest="plot_data")
    #parser.add_option("-n", "--pnumber",
    #                  help="specify pixel number to print [and plot]", dest="p_number")
    #parser.add_option("-r", "--header", action="store_true",
    #                  help="print headers", dest="print_headers")

    #(options, args) = parser.parse_args()

    #if len(sys.argv[1:]) == 0:
    #    parser.error("at least the filename parameter must be informed.")
    #    parser.print_help()
    #if options.quiet:
    #    sys.stdout = Nop()
    
    rootgrp = Dataset(filename, "r")
    data = rootgrp.variables["array_data"][:]

    print("-"*80)
    print("File name:", filename)
    print("-"*80)
    print("Total Data Shape:", data.shape)
    #if (options.p_number != None):
    #    print("Printing pixel:", options.p_number)
    print("-"*80)

    global next_pos

    for ds0 in data:
        ds0 = ds0[0]
        #if(options.print_headers):
        #    print("-"*80)
        #    print("Dataset Shape: ", ds0.shape)
        #    print("-"*80)
        #    print("Header")
        #    print("-"*80)
        next_pos = 256
        number_pixels = read_header(ds0, False)#options.print_headers)
        for i in range(number_pixels):
            next_pos = read_pixel_block(ds0, i, next_pos, False, False) #options.plot_data, options.p_number)

    print("-"*80)
    file_name = filename
    try_number = 2
    while(os.path.isfile('/home/iss/workspace/mcaFile/' + file_name)):
        file_name = filename + '-' + str(try_number)
        try_number += 1

    print("Creating file for channel 1...")
    np.savetxt(file_name + '-chan1.txt', exporting_array1, fmt='%i',delimiter=' ')
    print("Creating file for channel 2...")
    np.savetxt(file_name + '-chan2.txt', exporting_array2, fmt='%i',delimiter=' ')
    print("Creating file for channel 3...")
    np.savetxt(file_name + '-chan3.txt', exporting_array3, fmt='%i',delimiter=' ')
    print("Creating file for channel 4...")
    np.savetxt(file_name + '-chan4.txt', exporting_array4, fmt='%i',delimiter=' ')

if __name__ == "__main__":
    main()

