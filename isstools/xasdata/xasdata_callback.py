from bluesky.callbacks import CallbackBase
from isstools.xasdata.xasdata_lite import (xasdata_load_dataset_from_files,
                                           xasdata_bin_dataset, xasdata_interpolate_dataset)

class ProcessingCallback(CallbackBase):
    def __init__(self,db, axis, canvas):
        self.db = db
        self.axis = axis
        self.canvas = canvas
        super().__init__()

    def stop(self, doc):
        print(f'Stop document {doc}')
        raw_datatable = xasdata_load_dataset_from_files(self.db, doc['run_start'])
        interpolated_datatable = xasdata_interpolate_dataset(raw_datatable)
        print(interpolated_datatable)
        self.axis.plot(interpolated_datatable['energy'], interpolated_datatable['iff'] / interpolated_datatable['i0'])
        self.canvas.draw_idle()
        super().stop(doc)