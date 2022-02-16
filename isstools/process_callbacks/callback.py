
from bluesky.callbacks import CallbackBase
from xas.process import process_interpolate_bin
import time as ttime

class ScanProcessingCallback(CallbackBase):
    def __init__(self, db, draw_func_interp, draw_func_bin, cloud_dispatcher,thread, print_func=None):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_bin = draw_func_bin
        self.cloud_dispatcher = cloud_dispatcher
        self.thread = thread
        if print_func is None:
            self.print = print
        else:
            self.print = print_func
        super().__init__()

    def stop(self, doc):
        # print(f" {ttime.ctime()} >>>>>>>>>>  RUN EXIT STATUS : {doc['exit_status']}")
        if doc['exit_status'] == 'success':
            #process_interpolate_bin(doc, self.db, self.draw_func_interp, self.draw_func_bin, self.cloud_dispatcher)
            self.thread.doc = doc
            self.thread.start()
        else:
            reason = doc['reason']
            self.print(f'Scan failed, reason: {reason}')


