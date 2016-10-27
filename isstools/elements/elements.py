import epics


class shutter(epics.PV):
    def __init__(self, pvname, open_pv = None, close_pv = None, *args, **kwargs):
        super().__init__(pvname, *args, **kwargs)
        self.open_pv = open_pv
        self.close_pv = close_pv

    def open(self):
        if self.open_pv is not None:
            print('opening')
            temp_pv = epics.PV(self.open_pv)
            temp_pv.put(1)
            
    def close(self):
        if self.close_pv is not None:
            print('closing')
            temp_pv = epics.PV(self.close_pv)
            temp_pv.put(1)

    #def put(self, *args, **kwargs):
    #    if self.write_pv is not None:
    #        print(self.write_pv, args[0])
    #        temp_pv = epics.PV(self.write_pv)
    #        temp_pv.put(args[0])
    #    else:
    #        super().put(*args, **kwargs)
