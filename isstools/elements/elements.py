import epics


class shutter(epics.PV):
    def __init__(self, write_pv = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.write_pv = write_pv
        print(write_pv)

    def put(self, *args, **kwargs):
        if self.write_pv is not None:
            temp_pv = epics.PV(self.write_pv)
            print(*args)
            temp_pv.put(value)
        else:
            super().put(*args, **kwargs)
