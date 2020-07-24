import matplotlib.pyplot as plt
import numpy as np
import bluesky.plan_stubs as bps
import os
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


cam_sp1_calib_file = '/nsls2/xf08id/Sandbox/camera_calibration_images/cam1_data.dat'
cam_sp2_calib_file = '/nsls2/xf08id/Sandbox/camera_calibration_images/cam2_data.dat'


def save_shots_from_cameras(cam_dict, stage_handle, cam_names=['camera_sample1', 'camera_sample2'],
                            fpath=r'/nsls2/xf08id/Sandbox/camera_calibration_images/'):
    for name in cam_names:
        cam = cam_dict[name]
        im = cam.image.image
        giant_x = stage_handle.x.get()[0]
        giant_y = stage_handle.y.get()[0]

        fname = name + '_' + str(giant_x) + '_' + str(giant_y) + '.dat'
        print(fname)
        # plt.figure()
        # plt.imshow(im)
        np.savetxt(fpath + fname, im)


def take_stage_calibration_data(cam_dict, stage_handle, RE,
                                cam_names=['camera_sample2'],
                                limits=[155, 283, -72, 10], n=7):
    print(limits)
    xlo, xhi, ylo, yhi = limits

    xs = np.linspace(xlo, xhi, n)
    ys = np.linspace(ylo, yhi, n)
    X, Y = np.meshgrid(xs, ys)
    XY = np.hstack((X.ravel()[:, None], Y.ravel()[:, None]))

    for xy in XY:
        print('moving to', xy)
        RE(bps.mv(stage_handle.x, xy[0]))
        RE(bps.mv(stage_handle.y, xy[1]))
        RE(bps.sleep(1.0))
        save_shots_from_cameras(cam_dict, stage_handle, cam_names=cam_names)


def analyze_calibration_data(file_base='camera_sample1', fpath=r'/nsls2/xf08id/Sandbox/camera_calibration_images/'):

    gen = os.walk(fpath)
    flist_all = [i for i in gen][0][2]
    flist = [i for i in flist_all if i.startswith(file_base)]
    data = np.zeros((len(flist), 5))
    print(data.shape)
    for i, f in enumerate(flist):
        image = np.genfromtxt(fpath + f)
        bla = image.argmax()
        pix_max_y, pix_max_x = np.unravel_index(bla, image.shape)
        intensity = image[pix_max_y, pix_max_x]
        words = f.split('_')
        stage_x = words[-2]
        stage_y = words[-1][:-4]
        print(stage_x, stage_y, pix_max_x, pix_max_y, intensity)
        data[i, 0] = stage_x
        data[i, 1] = stage_y
        data[i, 2] = pix_max_x
        data[i, 3] = pix_max_y
        data[i, 4] = intensity
    return data


class Converter:

    def __init__(self, x0, y0, x1, y1, n=3, check_quality=False):
        self.n = n

        V0 = self.generate_basis(x0, y0)
        V1 = self.generate_basis(x1, y1)

        self.coef0_x1 = self.generate_coefs(V0, x1)
        self.coef0_y1 = self.generate_coefs(V0, y1)

        self.coef1_x0 = self.generate_coefs(V1, x0)
        self.coef1_y0 = self.generate_coefs(V1, y0)

        if check_quality:
            self._check_quality(x0, y0, x1, y1)


    def _check_dim(self, a):
        if (type(a)== int) or (type(a)==float) or (a.ndim == 0):
            return a[None, None]
        elif a.ndim == 1:
            return a[:, None]


    def generate_basis(self, x, y):
        m = x.size
        x = self._check_dim(x)
        y = self._check_dim(y)
        basis_list = [np.ones((m, 1))] + \
                     [np.hstack([x ** i * y ** (j - i) for i in range(j+1)]) for j in range(1, self.n + 1)]
        return np.hstack(basis_list)


    def generate_coefs(self, V, z):
        coefs, _, _, _ = np.linalg.lstsq(V, z, rcond=-1)
        return coefs


    def convert_01(self, x0, y0):
        basis0 = self.generate_basis(x0, y0)
        x1 = basis0 @ self.coef0_x1
        y1 = basis0 @ self.coef0_y1
        return x1, y1


    def convert_10(self, x1, y1):
        basis1 = self.generate_basis(x1, y1)
        x0 = basis1 @ self.coef1_x0
        y0 = basis1 @ self.coef1_y0
        return x0, y0


    def _generate_grid(self, x, y, factor=3):
        m = x.size
        __x_grid = np.linspace(x.min(), x.max(), m * factor + 1)
        __y_grid = np.linspace(y.min(), y.max(), m * factor + 1)
        _x_grid, _y_grid = np.meshgrid(__x_grid, __y_grid)
        return _x_grid.ravel(), _y_grid.ravel()


    def _check_quality(self, x0, y0, x1, y1):

        x0_grid, y0_grid = self._generate_grid(x0, y0)
        x1_grid, y1_grid = self._generate_grid(x1, y1)

        V0_grid = self.generate_basis(x0_grid, y0_grid)
        V1_grid = self.generate_basis(x1_grid, y1_grid)

        x0_pred = V1_grid @ self.coef1_x0
        y0_pred = V1_grid @ self.coef1_y0
        x1_pred = V0_grid @ self.coef0_x1
        y1_pred = V0_grid @ self.coef0_y1


        fig = plt.figure(666)
        ax = fig.add_subplot(221, projection='3d')
        plt.plot(x0, y0, x1, 'k.')
        plt.plot(x0_grid, y0_grid, x1_pred, 'r.', ms=1, alpha=0.3)
        plt.title('(x0, y0)->x1')

        ax = fig.add_subplot(222, projection='3d')
        plt.plot(x0, y0, y1, 'k.')
        plt.plot(x0_grid, y0_grid, y1_pred, 'r.', ms=1, alpha=0.3)
        plt.title('(x0, y0)->y1')

        ax = fig.add_subplot(223, projection='3d')
        plt.plot(x1, y1, x0, 'k.')
        plt.plot(x1_grid, y1_grid, x0_pred, 'r.', ms=1, alpha=0.3)
        plt.title('(x1, y1)->x0')

        ax = fig.add_subplot(224, projection='3d')
        plt.plot(x1, y1, y0, 'k.')
        plt.plot(x1_grid, y1_grid, y0_pred, 'r.', ms=1, alpha=0.3)
        plt.title('(x1, y1)->y0')





def create_converters():
    cam_sp1_data = np.genfromtxt(cam_sp1_calib_file)
    cam_sp2_data = np.genfromtxt(cam_sp2_calib_file)

    c1 = Converter()



