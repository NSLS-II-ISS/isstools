from bluesky.callbacks import CallbackBase
from xas.process import process_interpolate_bin
from event_model import RunRouter, Filler
from databroker.assets.handlers_base import HandlerBase
from collections import namedtuple


class FlyScanProcessingCallback(CallbackBase):
    def __init__(self, db, draw_func_interp, draw_func_bin):
        self.db = db
        self.draw_func_interp = draw_func_interp
        self.draw_func_bin = draw_func_bin
        super().__init__()

    def stop(self, doc):
        process_interpolate_bin(doc, self.db, self.draw_func_interp, self.draw_func_bin)


# class StepScanProcessingCallback(CallbackBase):
#     def __init__(self):
#         #self.draw_func_interp = draw_func_interp
#         #self.draw_func_bin = draw_func_bin
#         super().__init__()
#         self.data = {}
#         self.descriptors = {}
#         self.current_seq_num = None
#         self.counter = 0
#
#
#     def descriptor(self,doc):
#         doc_name = doc['name']
#         if  'devname' in doc['data_keys'][doc['name']]:
#             doc_devname = doc['data_keys'][doc['name']]['devname']
#             print(f'Doc uid{doc["uid"]}')
#             print(f'Doc devname {doc_devname}')
#             self.descriptors.update({doc_name:doc_devname})
#
#
#     def bulk_events(self, doc):
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print(doc)
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#         print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
#
#         self.counter +=1
#         # seq_num = doc['seq_num']
#         print(f'>>>>>>>>>>> Counter: {self.counter}')
#         # if seq_num == self.current_seq_num:
#         #     pass


# New handlers to support reading files into a Pandas dataframe
class PizzaBoxAnHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'index', 'adc'], sep=' ')

    def __call__(self):
        return self.df

class PizzaBoxDIHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'encoder', 'index', 'di'], sep=' ')

    def __call__(self):
        return self.df

class PizzaBoxEncHandlerTxtPD(HandlerBase):
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath):
        self.df = pd.read_table(fpath, names=['ts_s', 'ts_ns', 'encoder', 'index', 'state'], sep=' ')

    def __call__(self):
        return self.df

class PizzaBoxEncHandlerTxt(HandlerBase):
    encoder_row = namedtuple('encoder_row',
                             ['ts_s', 'ts_ns', 'encoder', 'index', 'state'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.encoder_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxDIHandlerTxt(HandlerBase):
    di_row = namedtuple('di_row', ['ts_s', 'ts_ns', 'encoder', 'index', 'di'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.di_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxAnHandlerTxt(HandlerBase):
    encoder_row = namedtuple('encoder_row', ['ts_s', 'ts_ns', 'index', 'adc'])
    "Read PizzaBox text files using info from filestore."

    bases = (10, 10, 10, 16)
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):

        cs = self.chunk_size
        return [self.encoder_row(*(int(v, base=b) for v, b in zip(ln.split(), self.bases)))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


def step_scan_factory(name, start_doc):
    filler = Filler({'PIZZABOX_AN_FILE_TXT_PD': PizzaBoxAnHandlerTxtPD,
                     'PIZZABOX_DI_FILE_TXT_PD': PizzaBoxDIHandlerTxtPD,
                     'PIZZABOX_ENC_FILE_TXT_PD': PizzaBoxEncHandlerTxtPD,
                     'PIZZABOX_AN_FILE_TXT': PizzaBoxAnHandlerTxt,
                     'PIZZABOX_DI_FILE_TXT': PizzaBoxDIHandlerTxt,
                     'PIZZABOX_ENC_FILE_TXT': PizzaBoxEncHandlerTxt})

    def cb(name, doc):
        filler(name, doc)  # Fill in place any externally-stored data written by area detector.
        if True:  # name == 'bulk_events':
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print(doc)
            print(name)
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')

    return [cb], []

run_router = RunRouter([step_scan_factory])