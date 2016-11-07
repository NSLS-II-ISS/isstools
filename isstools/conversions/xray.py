import numpy as np

def k2e(k, E0):
    return ((1000/(16.2009 ** 2)) * (k ** 2)) + E0#(1000 * ((k ** 2) + (16.2009 ** 2) * E0/1000) / (16.2009 ** 2)) - E0

def e2k(E, E0):
    return 16.2009 * (((E - E0)/1000) ** 0.5)

def encoder2energy(encoder, offset = 0):
    return -12400 / (2 * 3.1356 * np.sin(np.deg2rad((encoder/360000) + float(offset))))

def energy2encoder(energy, offset = 0):
    return 360000 * (np.degrees(np.arcsin(-12400 / (2 * 3.1356 * energy))) - offset)
