from bluesky.callbacks import CallbackBase
from xasdata import process


class ProcessingCallback(CallbackBase):
    def __init__(self, db, draw_func):
        self.db = db
        self.draw_func = draw_func
        super().__init__()

    def stop(self, doc):
        process(doc, self.db, self.draw_func)