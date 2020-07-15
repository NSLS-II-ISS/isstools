import matplotlib.pyplot as plt
import numpy as np
import bluesky.plan_stubs as bps
import os


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


def take_stage_calibration_data(cam_dict, stage_handle, RE, limits=[130.209 , 263.109, -52.066, 34.634], n=25):

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
        save_shots_from_cameras(cam_dict, stage_handle)


def analyze_calibration_data(fpath=r'/nsls2/xf08id/Sandbox/camera_calibration_images/'):

    gen = os.walk(fpath)
    flist = [i for i in gen][0][2]
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



