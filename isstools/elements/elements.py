import epics


class shutter(epics.PV):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

