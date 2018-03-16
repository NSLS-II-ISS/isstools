import numpy as np
from databroker.assets.handlers_base import HandlerBase

# TODO : choose more uniform convention of SPEC's
class ISSTraceReader(HandlerBase):
    SPEC="ISS_Trace"
    def __init__(self, fpath):
        self._fpath = fpath
        self._data = np.loadtxt(fpath, comments="#")

    def __call__(self):
        return self._data

class ISSDATReader(HandlerBase):
    SPEC="ISS_Dat"
    def __init__(self, fpath):
        self._fpath = fpath
        self._data = np.loadtxt(fpath, comments="#")

    def __call__(self):
        return self._data
