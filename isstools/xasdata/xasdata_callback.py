from bluesky.callbacks import CallbackBase
from isstools.xasdata.xasdata_lite import (xasdata_load_dataset_from_files,
                                           xasdata_bin_dataset, xasdata_interpolate_dataset)

class ProcessingCallback(CallbackBase):
    def __init__(self, db, draw_func):
        self.db = db
        self.draw_func = draw_func
        super().__init__()

    def stop(self, doc):
        if 'experiment' in self.db[doc['run_start']].start.keys():
            if self.db[doc['run_start']].start['experiment'] == 'fly_energy_scan':
                raw_df = xasdata_load_dataset_from_files(self.db, doc['run_start'])
                interpolated_df = xasdata_interpolate_dataset(raw_df)
                self.draw_func(interpolated_df)