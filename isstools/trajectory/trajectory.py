# Temperature-conversion program using PyQt
import numpy as np
import matplotlib.pyplot as plt
import pkg_resources
import scipy
from scipy import interpolate
import math
from PyQt5 import QtCore

import time as ttime
#import pexpect
from pexpect import pxssh
from ftplib import FTP

from isstools.conversions import xray
import pandas as pd

class trajectory():
    def __init__(self):
        self.energy_grid = []
        self.encoder_grid = []


    def define(self, edge_energy = 11564, offsets = ([-200,-30,50,1000]),velocities = ([200, 20, 200]), stitching = ([75, 75, 10, 10, 100, 100]),
              servocycle = 16000, padding_lo = 1, padding_hi=1, trajectory_type = 'Step', sine_duration = 20, dsine_preedge_duration = 10,
              dsine_postedge_duration = 20, vel_edge = 10):

        self.servocycle=servocycle
        if trajectory_type == 'Step':
            preedge_lo = edge_energy+offsets[0]
            preedge_hi = edge_energy+offsets[1]
            edge_lo = preedge_hi
            edge_hi = edge_energy+offsets[2]
            postedge_lo = edge_hi
            postedge_hi = edge_energy+offsets[3]
            velocity_preedge = velocities[0]
            velocity_edge = velocities[1]
            velocity_postedge = velocities[2]
    
            preedge_stitch_lo = preedge_lo + stitching[0] #
            preedge_stitch_hi = preedge_hi - stitching[1] #
            edge_stitch_lo = edge_lo + stitching[2] #
            edge_stitch_hi = edge_hi - stitching[3] #
            postedge_stitch_lo = postedge_lo + stitching[4] #
            postedge_stitch_hi = postedge_hi - stitching[5] #
    
            # create padding points to ensure derivative is zero
            t_padding_lo = 0
            e_padding_lo = (1 - ((padding_lo/2.5) * 0.0125)) * preedge_lo#preedge_lo-20
    
            #create preedge
            t_current = padding_lo
            t_preedge_lo = t_current + (-preedge_lo + preedge_stitch_lo) / velocity_preedge
            e_preedge_lo = preedge_stitch_lo
            t_preedge_hi = t_current + (-preedge_lo + preedge_stitch_hi) / velocity_preedge
            e_preedge_hi = preedge_stitch_hi
            e_step = 1
            e_preedge = np.arange(e_preedge_lo, e_preedge_hi + e_step, e_step) 
            t_step = (t_preedge_hi - t_preedge_lo) / (len(e_preedge) - 1)
            t_preedge = np.arange(t_preedge_lo, t_preedge_hi + (t_step / 2), t_step) 
    
    
            t_current = t_current + (-preedge_lo + preedge_hi) / velocity_preedge
            t_edge_lo = t_current + (-edge_lo + edge_stitch_lo) / velocity_edge
            e_edge_lo = edge_stitch_lo
            t_edge_hi = t_current + (-edge_lo + edge_stitch_hi) / velocity_edge
            e_edge_hi = edge_stitch_hi
            e_step = 1
            e_edge = np.arange(e_edge_lo, e_edge_hi + e_step, e_step) 
            t_step = (t_edge_hi - t_edge_lo) / (len(e_edge) - 1)
            t_edge = np.arange(t_edge_lo, t_edge_hi + (t_step / 2), t_step) 
    
    
            t_current = t_current + (-edge_lo + edge_hi) / velocity_edge
            t_postedge_lo = t_current + (-postedge_lo + postedge_stitch_lo) / velocity_postedge
            e_postedge_lo = postedge_stitch_lo
            t_postedge_hi = t_current + (-postedge_lo + postedge_stitch_hi) / velocity_postedge
            e_postedge_hi = postedge_stitch_hi
            e_step = 1
            e_postedge = np.arange(e_postedge_lo, e_postedge_hi + e_step, e_step) 
            t_step = (t_postedge_hi - t_postedge_lo) / (len(e_postedge) - 1)
            t_postedge = np.arange(t_postedge_lo, t_postedge_hi + (t_step / 2), t_step) 
    
    
            t_current = t_current + (-postedge_lo + postedge_hi) / velocity_postedge
            t_padding_hi = t_current + padding_hi
            e_padding_hi = (1 + ((padding_hi/2.5) * 0.0125)) * postedge_hi #postedge_hi+20
    
            # concatenate the arrays
            #self.time = np.array([t_padding_lo, t_preedge_lo, t_preedge_hi, \
            #                      t_edge_lo, t_edge_hi, t_postedge_lo, t_postedge_hi, t_padding_hi])
            self.time = np.concatenate(([t_padding_lo], t_preedge, t_edge, t_postedge, [t_padding_hi]))
            #self.energy = np.array([e_padding_lo, e_preedge_lo, e_preedge_hi,\
            #                        e_edge_lo, e_edge_hi, e_postedge_lo, e_postedge_hi,e_padding_hi])
            self.energy = np.concatenate(([e_padding_lo], e_preedge, e_edge, e_postedge, [e_padding_hi]))


        elif trajectory_type == 'Sine':
            total_time = float(sine_duration)
            preedge_lo = edge_energy+offsets[0]
            postedge_hi = edge_energy+offsets[3]
            x = np.linspace(-np.pi / 2, np.pi / 2, 100)
            energy = (np.sin(x) * (postedge_hi - preedge_lo) / 2) + (postedge_hi + preedge_lo) / 2
            time = np.linspace(0, total_time, 100)
            self.energy = energy
            self.time = time

        elif trajectory_type == 'Double Sine/Constant Edge':
            edge_duration = (offsets[2] - offsets[1]) / vel_edge
            total_time = float(dsine_preedge_duration) + float(edge_duration) + float(dsine_postedge_duration)
            preedge_dur = float(dsine_preedge_duration) / total_time
            edge_dur = float(edge_duration) / total_time
            postedge_dur = float(dsine_postedge_duration) / total_time
            preedge_lo = edge_energy + offsets[0]
            preedge_hi = edge_energy + offsets[1]
            postedge_lo = edge_energy + offsets[2]
            postedge_hi = edge_energy + offsets[3]
            edge = edge_energy

            x1_num = int(np.round(preedge_dur * 1000))
            xedge_num = int(np.round(edge_dur * 1000))
            x2_num = int(np.round(postedge_dur * 1000))
            x1 = np.linspace(-np.pi / 2, (3 * np.pi / 2), x1_num)
            x2 = np.linspace(-np.pi / 2, (3 * np.pi / 2), x2_num)


            time1 = np.linspace(0, (preedge_dur * total_time), 2 * len(x1))
            time_int = np.linspace((preedge_dur * total_time) + (time1[1] - time1[0]), (preedge_dur * total_time) + (edge_dur * total_time), 2 * xedge_num)
            time2 = np.linspace(time_int[-1] + (time_int[1] - time_int[0]), total_time, 2 * len(x2))
            self.time = np.concatenate((time1, time_int, time2))

            m_factor = 1
            m_factor_der = 0.005
            pos1 = [0, 1000 + abs(preedge_hi - preedge_lo)]
            last_error = abs((pos1[-1] - pos1[0]) - (preedge_hi - preedge_lo))
            while abs((pos1[-1] - pos1[0]) - (preedge_hi - preedge_lo)) > 0.5:
                accel1_1 = m_factor * (preedge_hi - preedge_lo) * (np.sin(x1) + 1) / 1000
                factor = (max(accel1_1) - (vel_edge * (time_int[1] - time_int[0]))) / max(accel1_1)
                accel1_2 = -factor * m_factor * (preedge_hi - preedge_lo) * (np.sin(x1) + 1) / 1000

                vel1_1 = scipy.integrate.cumtrapz(accel1_1 * (1 / (x1_num/2)), initial = 0)
                vel1_2 = scipy.integrate.cumtrapz(accel1_2 * (1 / (x1_num/2)), initial = 0) + vel1_1[-1]

                vel1 = np.concatenate((vel1_1, vel1_2))
                pos1 = scipy.integrate.cumtrapz(vel1, initial = 0) + preedge_lo
                #print("1:", abs((pos1[-1] - pos1[0]) - (preedge_hi - preedge_lo)), m_factor)
                error = abs((pos1[-1] - pos1[0]) - (preedge_hi - preedge_lo))
                if(error > last_error):
                    m_factor_der = -(m_factor_der / 2)
                m_factor += m_factor_der
                last_error = error

            vel_int = np.array([np.diff(time_int)[0]/np.diff(time1)[0] * vel1_2[-1]] * xedge_num * 2)
            pos_int = scipy.integrate.cumtrapz(vel_int, initial = 0) + pos1[-1] + (pos1[-1] - pos1[-2])

            m_factor = 1
            m_factor_der = 0.005
            pos2 = [0, 1000 + abs(postedge_hi - postedge_lo)]
            last_error = abs((pos2[-1] - pos2[0]) - (postedge_hi - postedge_lo))
            while abs((pos2[-1] - pos2[0]) - (postedge_hi - postedge_lo)) > 0.5:
                accel2_1 = m_factor * (postedge_hi - postedge_lo) * (np.sin(x2) + 1) / 1000
                acc_factor = m_factor * (postedge_hi - postedge_lo) * (np.sin(x2) + 1) / 1000
                accel2_2 = - acc_factor * (((vel_int[0] * len(acc_factor) / 2) + sum(acc_factor)) / sum(acc_factor))

                time_adj = np.diff(time2)[0]/np.diff(time_int)[0]
                vel2_1 = scipy.integrate.cumtrapz(accel2_1 * (1 / (x2_num/2)), initial = 0) + time_adj * vel_int[-1]
                vel2_2 = scipy.integrate.cumtrapz(accel2_2 * (1 / (x2_num/2)), initial = 0) + vel2_1[-1]
                vel2 = np.concatenate((vel2_1, vel2_2))
                pos2 = scipy.integrate.cumtrapz(vel2, initial = 0) + pos_int[-1] + (pos_int[-1] - pos_int[-2])
                #print("2:", abs((pos2[-1] - pos2[0]) - (postedge_hi - postedge_lo)), m_factor)
                error = abs((pos2[-1] - pos2[0]) - (postedge_hi - postedge_lo))
                if(error > last_error):
                    m_factor_der = -(m_factor_der / 2)
                m_factor += m_factor_der
                last_error = error

            self.energy = np.concatenate((pos1, pos_int, pos2))

        elif trajectory_type == 'Double Sine':
            total_time = float(dsine_preedge_duration) + float(dsine_postedge_duration)
            half = float(dsine_preedge_duration) / total_time
            preedge_lo = edge_energy + offsets[0]
            postedge_hi = edge_energy + offsets[3]
            edge = edge_energy

            x1_num = np.round(half * 100)
            x2_num = np.round((1 - half) * 100)
            x1 = np.linspace(-np.pi / 2, (3 * np.pi / 2), x1_num) #2 * half / x_step1)
            x2 = np.linspace(-np.pi / 2, (3 * np.pi / 2), x2_num) #2 * (1 - half) / x_step1)

            accel1 = (edge_energy - preedge_lo) * (np.sin(x1) + 1) #39.584072231342851
            accel2 = (postedge_hi - edge_energy) * (np.sin(x2) + 1)
            accel1 = np.concatenate((accel1, -accel1))
            accel2 = np.concatenate((accel2, -accel2))

            vel1 = scipy.integrate.cumtrapz(accel1 * (1 / x1_num), initial = 0)
            vel2 = scipy.integrate.cumtrapz(accel2 * (1 / x2_num), initial = 0)

            pos1 = scipy.integrate.cumtrapz(vel1 * (1 / x1_num), initial = 0) + preedge_lo
            pos1 = (pos1 / pos1[len(pos1) - 1]) * edge
            pos2 = scipy.integrate.cumtrapz(vel2 * (1 / x2_num), initial = 0) + edge

            self.energy = np.concatenate((pos1, pos2))

            time = np.linspace(0, (half * total_time), 2 * len(x1))
            time2 = np.linspace((half * total_time) + (time[1] - time[0]), total_time, 2 * len(x2))
            self.time = np.concatenate((time, time2))


    def interpolate(self):
        cs = interpolate.CubicSpline(self.time, self.energy, bc_type='clamped')
        self.time_grid = np.arange(self.time[0], self.time[-1], 1 / self.servocycle)
        self.energy_grid=cs(self.time_grid)
        self.energy_grid_der=np.diff(self.energy_grid)/(self.time_grid[1] - self.time_grid[0])

    def revert(self):
        self.energy = self.energy[::-1]
        self.energy_grid = self.energy_grid[::-1]
        self.energy_grid_der = self.energy_grid_der[::-1]

    def tile (self,reps = 1, single_direction = False):
        if not single_direction:
            self.time_grid = np.append(self.time_grid, (self.time_grid + self.time_grid[-1]))
            self.energy_grid = np.append(self.energy_grid, np.flipud(self.energy_grid))
        self.time_grid = np.tile(self.time_grid, reps)
        self.energy_grid = np.tile(self.energy_grid, reps)

    def e2encoder(self, offset):
        self.encoder_grid = -xray.energy2encoder(self.energy_grid, offset) 

    def e2energy(self, offset):
        self.energy_grid = -xray.encoder2energy(self.encoder_grid, offset)


    def plot(self):
        plt.plot(self.time, self.energy, 'r+')
        plt.plot(self.energy_grid,'b')
        plt.show()

    def load_trajectory_file(self, filename, offset, is_energy):
        array_out=[]
        with open(str(filename)) as f:
            for line in f:
                array_out.append(float(line))
        array_out = np.array(array_out)
        if is_energy:
            self.energy_grid_loaded = array_out
        else:
            self.energy_grid_loaded = -xray.encoder2energy(array_out, offset)
            
        


class trajectory_manager():
    def __init__(self, hhm, **kwargs):
        self.hhm = hhm
        self.traj_info = {}

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
    def load(self, orig_file_name, new_file_path, is_energy, offset, new_file_name = 'hhm.txt', orig_file_path = '/GPFS/xf08id/trajectory/', ip = '10.8.2.86'):

        print('[Load Trajectory] Starting...')

        # Check if new_file_path is between the possible values
        if int(new_file_path) > 9 or int(new_file_path) < 1:
            print("[Load Trajectory] Path '{}' not possible. Please use a value in the range 1 <= new_file_path <= 9.".format(new_file_path))
            return False
   
        # Get number of lines in file
        file_size = self.file_len(orig_file_path + orig_file_name)
        print('[Load Trajectory] Number of lines in file: {}'.format(file_size))

        # Get min and max of trajectory in eV
        if orig_file_path[-1] != '/':
            fp += '/'

        traj = pd.read_table('{}{}'.format(orig_file_path, orig_file_name), header=None)
        name = orig_file_name
        if is_energy:
            min_energy = int(np.round(traj).min())
            max_energy = int(np.round(traj).max())
            enc = np.int64(np.round(xray.energy2encoder(-traj, -offset)))
            orig_file_name = '.energy_traj_aux.txt'
            np.savetxt('{}{}'.format(orig_file_path, orig_file_name), enc, fmt='%d')
        else:
            min_energy = int(xray.encoder2energy((-traj).min()))
            max_energy = int(xray.encoder2energy((-traj).max()))

        print('[Load Trajectory] Min energy: {}'.format(min_energy))
        print('[Load Trajectory] Max energy: {}'.format(max_energy))

        # Create ftp connection with default credential
        ftp = FTP(ip)
        ftp.login()
        s = pxssh.pxssh()
        ssh_login = s.login (ip, 'root', 'deltatau')


        if ssh_login:
            # Check if the directory exists in /usrflash/lut/. If it does not, create it.
            if str(new_file_path) != '':
                ftp.cwd('/usrflash/')
                dir_list = ftp.nlst()
                dir_exists = 0
                for dir_name in dir_list:
                    if dir_name == 'lut':
                        dir_exists = 1
                if not dir_exists:
                    print('[Load Trajectory] mkdir: /usrflash/lut')
                    ftp.mkd('/usrflash/lut')
                    s.sendline ('chown ftp:root /var/ftp/usrflash/lut')
                    s.sendline ('chmod a+wrx /var/ftp/usrflash/lut')

                ftp.cwd('/usrflash/lut/')
                dir_list = ftp.nlst()
                dir_exists = 0
                for dir_name in dir_list:
                    if dir_name == str(new_file_path):
                        dir_exists = 1
                if not dir_exists:
                    print('[Load Trajectory] mkdir: /usrflash/lut/{}'.format(new_file_path))
                    ftp.mkd('/usrflash/lut/{}'.format(new_file_path))
                    s.sendline ('chown ftp:root /var/ftp/usrflash/lut/{}'.format(new_file_path))
                    s.sendline ('chmod a+wrx /var/ftp/usrflash/lut/{}'.format(new_file_path))

                s.sendline ('chown ftp:root /var/ftp/usrflash/lut/{}/hhm.txt'.format(new_file_path))
                s.sendline ('chmod 777 /var/ftp/usrflash/lut/{}/hhm.txt'.format(new_file_path))

            ftp_file_path = '/var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name)

        # Open file and transfer to the power pmac
            f = open(orig_file_path + str(orig_file_name), 'rb')
            if(f.readable()):
                result = ftp.storbinary('STOR ' + '/usrflash/lut/' + str(new_file_path) + '/' + new_file_name, f)
                if(result == '226 File receive OK.'):
                    print('[Load Trajectory] File sent OK')
                    s.sendline ('chown ftp:root /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                    s.sendline ('chmod a+wrx /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                    s.sendline ('echo "{}\n{}\n{}\n{}" > /var/ftp/usrflash/lut/{}/hhm-size.txt'.format(file_size, name, min_energy, max_energy, new_file_path))
                    ttime.sleep(0.01)
                    ftp.close()
                    print('[Load Trajectory] Permissions OK')

            s.logout()
            s.pid = None
            print('[Load Trajectory] Completed!')
        else:
            print('[Load Trajectory] Fail! Not able to ssh into the controller...')

    ########## init ##########
    # Transfer the trajectory from the flash to the ram memory in the controller
    # It must be called everytime you decide to use a different trajectory
    # arg1 = lut_number                -> lookup table number of the trajectory that will be used - must be a number between 1 and 9
    # arg2 (optional) = ip            -> IP of the controller that will receive the file. Default = '10.8.2.86'
    # arg3 (optional) = filename    -> Filename of the trajectory file in the controller. Currently, it MUST be 'hhm.txt'
    def init(self, lut_number, ip = '10.8.2.86', filename = 'hhm.txt'):

        print('[Init Trajectory] Starting...')

        self.hhm.lut_number.put(lut_number)

        ttime.sleep(0.5)
        while (int(self.hhm.lut_number_rbv.value) != int(lut_number)):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
    
        self.hhm.lut_start_transfer.put("1")    
        while (self.hhm.lut_transfering.value == 0):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
        while (self.hhm.lut_transfering.value == 1):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
        ttime.sleep(.25)
        #while (self.hhm.trajectory_loading.value == 0):
        #    ttime.sleep(.001)
        #    QtCore.QCoreApplication.processEvents()
        while (self.hhm.trajectory_loading.value == 1):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
    
        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/{}'.format(lut_number))
    
        file_list = ftp.nlst()
        file_exists = 0
        for file_name in file_list:
            if file_name == filename:
                file_exists = 1
        if file_exists == 0:
            print('[Init Trajectory] File not found. :(\nAre you sure \'{}\' is the correct lut number?'.format(lut_number))
        else:
            info = []
            def handle_binary(more_data):
                info.append(more_data)
    
            resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
            if(len(info) == 2):
                size = int(info[0])
                name = info[1]
            elif(len(info) == 4):
                size = int(info[0])
                name = info[1]
                min_en = int(info[2])
                max_en = int(info[3])
            else:
                print('[Init Trajectory] Could not find the size and name info in the controller. Please, try sending the trajectory file again using trajectory_load(...)')    
                return False
    
            if(size == 0):
                print('[Init Trajectory] Size seems to be equal to 0. Please, try sending the trajectory file again using trajectory_load(...)')
                return False
            else:
                self.hhm.cycle_limit.put(size)
                while (self.hhm.cycle_limit_rbv.value != size):
                    ttime.sleep(.01)
                print('[Init Trajectory] New lut number: {}\n[Init Trajectory] Trajectory name: {}\n[Init Trajectory] Number of points: {}\n[Init Trajectory] Completed!'.format(lut_number, name, size))
                self.hhm.trajectory_name.put(name)
    

    ########## read_info ##########
    # Function that prints info about the trajectories currently stored in the controller
    # arg1 (optional) = ip    -> IP of the controller. Default = '10.8.2.86'
    def read_info(self, ip = '10.8.2.86', silent=False):
        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/')
        if not silent:
            print('-'*62)
            print('The trajectories found in the controller (ip: {}) are:'.format(ip))
        self.traj_info.clear()
    
        def handle_binary(more_data):
            info.append(more_data)
    
        ret_txt = '' 
        for i in range(1, 10):
            ftp.cwd('/usrflash/lut/{}'.format(i))
    
            file_list = ftp.nlst()
            filename = 'hhm-size.txt'
            file_exists = 0
            for file_name in file_list:
                if file_name == filename:
                    file_exists = 1
            if file_exists == 1:

                info = []
          
                resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
                if(len(info) == 2):
                    size = int(info[0])
                    name = info[1]
                    self.traj_info[str(i)] = {'name':str(name), 'size':str(size)}
                    if not silent:
                        print('{}: {:<24} (Size: {})'.format(i, name, size))
                elif(len(info) == 4):
                    size = int(info[0])
                    name = info[1]
                    min_en = int(info[2])
                    max_en = int(info[3])
                    self.traj_info[str(i)] = {'name':str(name), 'size':str(size), 'min':str(min_en), 'max':str(max_en)}
                    if not silent:
                        print('{}: {:<24} (Size: {}, min: {}, max: {})'.format(i, name, size, min_en, max_en))
                else:
                    self.traj_info[str(i)] = {'name':'undefined', 'size':'undefined'}
                    if not silent:
                        print('{}: Could not find the size and name info'.format(i)) 
            elif not silent:
                self.traj_info[str(i)] = {'name':'undefined', 'size':'undefined'}
                print('{}: Could not find the size and name info'.format(i))    
    
        if not silent:
            print('-'*62)

        return self.traj_info
    

    def current_lut(self):
        return self.hhm.lut_number_rbv.value
        
