import os
import os.path

from bluesky.callbacks import CallbackBase
from xas.process import process_interpolate_bin
from event_model import RunRouter, Filler
from databroker.assets.handlers_base import HandlerBase
from collections import namedtuple
import pandas as pd
import numpy as np


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


DATA = {}
SEQ_NUM = 1

def step_scan_factory(name, start_doc):
    aliases = {'pba2_adc7': 'pba2_adc7',
                'pba1_adc6':'iff',
                'pba1_adc1': 'it',
                'pba2_adc6':'ir',
                'pba1_adc7':'i0',
                'hhm_energy':'energy',
                }

    filler = Filler({'PIZZABOX_AN_FILE_TXT_PD': PizzaBoxAnHandlerTxtPD,
                     'PIZZABOX_DI_FILE_TXT_PD': PizzaBoxDIHandlerTxtPD,
                     'PIZZABOX_ENC_FILE_TXT_PD': PizzaBoxEncHandlerTxtPD})

    export_fp = '/tmp/export.dat'
    if os.path.exists(export_fp):
        os.remove(export_fp)
        with open(export_fp, 'w') as f:
            f.write('# ')

    def cb(name, doc):
        global DATA
        global SEQ_NUM

        filler(name, doc)  # Fill in place any externally-stored data written by area detector.

        if name == 'event_page':
            seq_num = doc['seq_num'][0]
            if seq_num > SEQ_NUM:
                SEQ_NUM += 1
                print(f' &&&&&&&&&&&&&&&&&&&&& data {DATA}')
                res = pd.DataFrame(DATA)
                ##with open('/tmp/export.csv', 'w') as f:
                ##    res.to_csv(f, index=False, columns=res.columns[::-1])
                with open(export_fp, 'a') as f:
                    res.tail(n=1).to_csv(f, header=(f.tell() == 2), index=False, sep='\t', columns=res.columns[::-1])
                #print(f' Current number {seq_num}')
                #print(f' Global number {SEQ_NUM}')

            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            # print(doc)
            #print(name)

            dev = list(dict(doc['data']).keys())[0]
            print(f'>>>>>>>>>>>>>>>>>>>>>>>> Device {dev}')
            aliased_dev = aliases[dev]
            if aliased_dev not in DATA:
                DATA[aliased_dev] = []

            data = doc['data'][dev][0]
            #print(f'>>>>>>>>>>>>>>>>>>>>>>>> {dev} Data {data}')
            if dev == 'hhm_energy':
                data_dec = data
            elif dev in ['pba2_adc7', 'pba1_adc6', 'pba1_adc1', 'pba2_adc6', 'pba1_adc7']:
                #print('?????????????????????' , [x for x in data['adc']] )
                #print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%     ', type(data['adc']))

                data_dec = data['adc'].dropna().apply(
                    lambda x: (int(x, 16) >> 8) - 0x40000 if (int(x, 16) >> 8) > 0x1FFFF else int(x,16) >> 8) * 7.62939453125e-05
                data_dec = data_dec.mean()

            if dev in aliases.keys():
                DATA[aliased_dev].append(data_dec)

            #print(f'>>>>>>>>>>>>>>>>>>>>>>>> Data {data_dec}')

            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            #print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')

    return [cb], []

run_router = RunRouter([step_scan_factory])