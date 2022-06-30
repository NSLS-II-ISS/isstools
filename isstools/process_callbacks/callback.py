
from bluesky.callbacks import CallbackBase
from xas.process import process_interpolate_bin
import time as ttime

class ScanProcessingCallback(CallbackBase):
    def __init__(self, db, draw_func_interp, draw_func_bin, cloud_dispatcher, make_thread_func, print_func=None):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_bin = draw_func_bin
        self.cloud_dispatcher = cloud_dispatcher
        self.make_thread_func = make_thread_func
        if print_func is None:
            self.print = print
        else:
            def _print_func(msg):
                print_func(msg, tag='Processing', add_timestamp=True)
            self.print = _print_func
        super().__init__()

    def stop(self, doc):
        # print(f" {ttime.ctime()} >>>>>>>>>>  RUN EXIT STATUS : {doc['exit_status']}")
        if doc['exit_status'] == 'success':
            #process_interpolate_bin(doc, self.db, self.draw_func_interp, self.draw_func_bin, self.cloud_dispatcher)
            self.thread = self.make_thread_func()
            self.thread.finished.connect(self._delete_thread)
            self.thread.doc = doc
            self.thread.start()
        else:
            reason = doc['reason']
            self.print(f'Scan failed, reason: {reason}')

    def _delete_thread(self):
        self.print('Thread can be deleted now!!!!!!!!!!!')
        print('BLA BLA BLA BLA BLA BLA BLA BLA')


