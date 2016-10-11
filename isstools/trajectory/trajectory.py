# Temperature-conversion program using PyQt
import numpy as np
import matplotlib.pyplot as plt
import pkg_resources
from scipy import interpolate
import math

import time as ttime
#import pexpect
from pexpect import pxssh
from ftplib import FTP


class trajectory():
    def __init__(self):
        self.energy_grid = []
        self.encoder_grid = []


    def define(self, edge_energy = 11564, offsets = ([-200,-30,50,1000]),velocities = ([200, 20, 200]), stitching = ([75, 75, 10, 10, 100, 100]),
              servocycle = 16000, padding_lo = 1 ,padding_hi=1):
        preedge_lo = edge_energy+offsets[0]
        preedge_hi = edge_energy+offsets[1]
        edge_lo = preedge_hi
        edge_hi = edge_energy+offsets[2]
        postedge_lo = edge_hi
        postedge_hi = edge_energy+offsets[3]
        self.servocycle=servocycle
        velocity_preedge = velocities[0]
        velocity_edge = velocities[1]
        velocity_postedge = velocities[2]
        preedge_stitch_lo = preedge_lo + stitching[0]

        preedge_stitch_hi = preedge_hi - stitching[1]

        edge_stitch_lo = edge_lo + stitching[2]
        edge_stitch_hi = edge_hi - stitching[3]
        postedge_stitch_lo = postedge_lo + stitching[4]
        postedge_stitch_hi = postedge_hi - stitching[5]

        # create padding points to ensure derivative is zero
        t_padding_lo = 0
        e_padding_lo = preedge_lo-20

        #create preedge
        t_current = padding_lo
        t_preedge_lo = t_current + (-preedge_lo + preedge_stitch_lo) / velocity_preedge
        e_preedge_lo = preedge_stitch_lo
        t_preedge_hi = t_current + (-preedge_lo + preedge_stitch_hi) / velocity_preedge
        e_preedge_hi = preedge_stitch_hi


        t_current = t_current + (-preedge_lo + preedge_hi) / velocity_preedge
        t_edge_lo = t_current + (-edge_lo + edge_stitch_lo) / velocity_edge
        e_edge_lo = edge_stitch_lo
        t_edge_hi = t_current + (-edge_lo + edge_stitch_hi) / velocity_edge
        e_edge_hi = edge_stitch_hi

        t_current = t_current + (-edge_lo + edge_hi) / velocity_edge

        t_postedge_lo = t_current + (-postedge_lo + postedge_stitch_lo) / velocity_postedge
        e_postedge_lo = postedge_stitch_lo
        t_postedge_hi = t_current + (-postedge_lo + postedge_stitch_hi) / velocity_postedge
        e_postedge_hi = postedge_stitch_hi

        t_current = t_current + (-postedge_lo + postedge_hi) / velocity_postedge

        t_padding_hi = t_current + padding_hi
        e_padding_hi = postedge_hi+20

        # concatenate the arrays
        self.time = np.array([t_padding_lo, t_preedge_lo, t_preedge_hi, \
                              t_edge_lo, t_edge_hi, t_postedge_lo, t_postedge_hi, t_padding_hi])
        self.energy = np.array([e_padding_lo, e_preedge_lo, e_preedge_hi,\
                                e_edge_lo, e_edge_hi, e_postedge_lo, e_postedge_hi,e_padding_hi])



    def interpolate(self):
        cs = interpolate.CubicSpline(self.time,self.energy, bc_type='clamped')
        self.time_grid = np.arange(self.time[0], self.time[-1], 1 / self.servocycle)
        self.energy_grid=cs(self.time_grid)
        self.energy_grid_der=np.diff(self.energy_grid)


    def tile (self,reps = 1):
        self.time_grid = np.append(self.time_grid, (self.time_grid + self.time_grid[-1]))
        self.energy_grid = np.append(self.energy_grid, np.flipud(self.energy_grid))
        self.time_grid = np.tile(self.time_grid, reps)
        self.energy_grid = np.tile(self.energy_grid, reps)

    def e2encoder(self):
        self.encoder_grid = (360000 * (180 / np.pi) * (np.arcsin(12400 / (2 * 3.1356 * self.energy_grid))))


    def plot(self):
        plt.plot(self.time, self.energy, 'r+')
        plt.plot(self.energy_grid,'b')
        plt.show()


class trajectory_manager():
    def __init__(self, hhm, **kwargs):
        self.hhm = hhm

    # Function used to count the number of lines in a file
    def file_len(self, fname):
        with open(fname) as f:
            for i, l in enumerate(f):
                pass
        return i + 1

    ########## load ##########
    # Transfer the trajectory file to the motor controller
    # arg1 = orig_file_name             -> Filename of the trajectory: E.g.: 'traj_Cu_fast.txt'
    # arg2 = new_file_path              -> LUT number where the new trajectory file will be stored
    # arg3 (optional) = new_file_name     -> New name that will be used as filename in the controller. Currently, it MUST be 'hhm.txt'
    # arg4 (optional) = orig_file_path     -> Path to look for the file that will be transfered. Default = '/GPFS/xf08id/trajectory/'
    # arg5 (optional) = ip                 -> IP of the controller that will receive the file. Default = '10.8.2.86'
    def load(self, orig_file_name, new_file_path, new_file_name = 'hhm.txt', orig_file_path = '/GPFS/xf08id/trajectory/', ip = '10.8.2.86'):

        # Check if new_file_path is between the possible values
        if int(new_file_path) > 9 or int(new_file_path) < 1:
            print("Path '{}' not possible. Please use a value in the range 1 <= new_file_path <= 9.".format(new_file_path))
            return False
   
        # Get number of lines in file
        file_size = self.file_len(orig_file_path + orig_file_name)
        print('Number of lines in file: {}'.format(file_size))

        # Create ftp connection with default credential
        ftp = FTP(ip)
        ftp.login()
        s = pxssh.pxssh()
        s.login (ip, 'root', 'deltatau')

        # Check if the directory exists in '/usrflash/lut/. If it does not, create it.'
        if str(new_file_path) != '':
            ftp.cwd('/usrflash/lut/')
            dir_list = ftp.nlst()
            dir_exists = 0
            for dir_name in dir_list:
                if dir_name == str(new_file_path):
                    dir_exists = 1
            if not dir_exists:
                print('mkdir: /usrflash/lut/{}'.format(new_file_path))
                ftp.mkd('/usrflash/lut/{}'.format(new_file_path))
                s.sendline ('chown ftp:root /var/ftp/usrflash/lut/{}'.format(new_file_path))
                s.sendline ('chmod a+wrx /var/ftp/usrflash/lut/{}'.format(new_file_path))

        ftp_file_path = '/var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name)

        # Open file and transfer to the power pmac
        f = open(orig_file_path + str(orig_file_name), 'rb')
        if(f.readable()):
            result = ftp.storbinary('STOR ' + '/usrflash/lut/' + str(new_file_path) + '/' + new_file_name, f)
            if(result == '226 File receive OK.'):
                s.sendline ('chown ftp:root /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                s.sendline ('chmod a+wrx /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                s.sendline ('echo "{}\n{}" > /var/ftp/usrflash/lut/{}/hhm-size.txt'.format(file_size, orig_file_name, new_file_path))
                ttime.sleep(0.01)
                ftp.close()

        print('File sent successfully')
        return True

    ########## init ##########
    # Transfer the trajectory from the flash to the ram memory in the controller
    # It must be called everytime you decide to use a different trajectory
    # arg1 = lut_number                -> lookup table number of the trajectory that will be used - must be a number between 1 and 9
    # arg2 (optional) = ip            -> IP of the controller that will receive the file. Default = '10.8.2.86'
    # arg3 (optional) = filename    -> Filename of the trajectory file in the controller. Currently, it MUST be 'hhm.txt'
    def init(self, lut_number, ip = '10.8.2.86', filename = 'hhm.txt'):

        self.hhm.lut_number.put(lut_number)

        ttime.sleep(0.1)
        while (self.hhm.lut_number_rbv.value != lut_number):
            ttime.sleep(.01)
    
        self.hhm.lut_start_transfer.put("1")    
        while (self.hhm.lut_transfering.value == 0):
            ttime.sleep(.01)
        while (self.hhm.lut_transfering.value == 1):
            ttime.sleep(.01)
    
        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/{}'.format(lut_number))
    
        file_list = ftp.nlst()
        file_exists = 0
        for file_name in file_list:
            if file_name == filename:
                file_exists = 1
        if file_exists == 0:
            print('File not found. :(\nAre you sure \'{}\' is the correct lut number?'.format(lut_number))
        else:
            info = []
            def handle_binary(more_data):
                info.append(more_data)
    
            resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
            if(len(info) == 2):
                size = int(info[0])
                name = info[1]
            else:
                print('Could not find the size and name info in the controller. Please, try sending the trajectory file again using trajectory_load(...)')    
                return False
    
            if(size == 0):
                print('Size seems to be equal to 0. Please, try sending the trajectory file again using trajectory_load(...)')
                return False
            else:
                self.hhm.cycle_limit.put(size)
                while (self.hhm.cycle_limit_rbv.value != size):
                    ttime.sleep(.01)
                print('Transfer completed!\nNew lut number: {}\nTrajectory name: {}\nNumber of points: {}'.format(lut_number, name, size))
                return True
    

    ########## read_info ##########
    # Function that prints info about the trajectories currently stored in the controller
    # arg1 (optional) = ip    -> IP of the controller. Default = '10.8.2.86'
    def read_info(self, ip = '10.8.2.86'):
        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/')
        print('-'*62)
        print('The trajectories found in the controller (ip: {}) are:'.format(ip))
    
        def handle_binary(more_data):
            info.append(more_data)
    
        ret_txt = '' 
        for i in range(1, 10):
            ftp.cwd('/usrflash/lut/{}'.format(i))
    
            info = []
          
            resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
            if(len(info) == 2):
                size = int(info[0])
                name = info[1]
                print('{}: {:<24} (Size: {})'.format(i, name, size))
            else:
                print('{}: Could not find the size and name info'.format(i))    
    
        print('-'*62)

    def current_lut(self):
        return self.hhm.lut_number_rbv.value
        
