# Temperature-conversion program using PyQt
import numpy as np
import matplotlib.pyplot as plt
import pkg_resources
from scipy import interpolate


class trajectory():
    def __init__(self):
        pass


    def build(self, edge_energy = 11564, offsets = ([-200,-30,50,1000]),velocities = ([200, 20, 200]), stitching = ([75, 75, 10, 10, 100, 100]),
              servocycle = 16000, padding_lo = 1,padding_hi=1):
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

        t_padding_lo = 0
        t_padding_1 = padding_lo / 4
        t_padding_2 = padding_lo / 3
        e_padding_lo = preedge_lo

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
        e_padding_hi = postedge_hi

        self.time= np.array([t_padding_lo,t_padding_1,t_padding_2, t_preedge_lo, t_preedge_hi, t_edge_lo, t_edge_hi, t_postedge_lo, t_postedge_hi, t_padding_hi])
        self.energy = np.array([e_padding_lo,e_padding_lo,e_padding_lo, e_preedge_lo, e_preedge_hi, e_edge_lo,e_edge_hi, e_postedge_lo, e_postedge_hi, e_padding_hi])


    def interpolate(self):

        spl = interpolate.splrep(self.time,self.energy)
        self.time_grid = np.arange(self.time[0],self.time[-1],1/self.servocycle)
        self.energy_grid=interpolate.splev(self.time_grid,spl,der=0)

    def plot(self):
        plt.plot(self.time, self.energy, 'r+')
        plt.plot(self.time_grid, self.energy_grid,'b')
        plt.show()





