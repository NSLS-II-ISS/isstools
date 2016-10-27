import epics


class shutter(epics.PV):
    def __init__(self, pvname, callback = None, **kwargs):
        super().__init__(pvname = pvname, callback = callback, **kwargs)

