import time
import copy
import numpy
import logging

logger = logging.getLogger('iss_processor')
logging.basicConfig(level='DEBUG')

# DEFINE DATABASE

from databroker import Broker
from ophyd.sim import NumpySeqHandler

raw = Broker.named('iss')
processed = Broker.named('iss_analysis')  # makes a second, unique temporary Broker
raw.reg.register_handler("NPY_SEQ", NumpySeqHandler)
processed.reg.register_handler("NPY_SEQ", NumpySeqHandler)
raw.prepare_hook = lambda name, doc: copy.deepcopy(doc)

# PROCESSING

from event_model import compose_run


def is_applicable(start_doc):
    ...
    return True
    # return True or False


def my_analysis_function(arr, factor):
    return factor * numpy.sum(arr)


class Filler:
    def __init__(self, handler_registry):
        self.handler_registry = handler_registry
        self.handlers = {}
        self.datums = {}

    def __call__(self, name, doc):
        return name, getattr(self, name)(doc)

    def start(self, doc):
        return doc

    def resource(self, doc):
        handler_class = self.handler_registry[doc['spec']]
        handler = handler_class(doc['resource_path'],
                                root=doc['root'],
                                **doc['resource_kwargs'])
        self.handlers[doc['uid']] = handler
        return doc

    def datum(self, doc):
        self.datums[doc['datum_id']] = doc
        return doc

    def event(self, doc):
        for key, is_filled in doc['filled'].items():
            if not is_filled:
                datum_id = doc['data'][key]
                datum_doc = self.datums[datum_id]
                handler = self.handlers[datum_doc['resource']]
                actual_data = handler(**datum_doc['datum_kwargs'])
                doc['data'][key] = actual_data
                doc['filled'][key] = True
        return doc

    def descriptor(self, doc):
        return doc

    def stop(self, doc):
        return doc


class Processor:
    version = 1

    def __init__(self, factor):
        self.factor = factor

    def __call__(self, name, doc):
        return name, getattr(self, name)(doc)

    def start(self, doc):
        metadata = {'raw_uid': doc['uid'],
                    'processor_version': self.version,
                    'processor_parameters': {'factor': self.factor}}
        self.compose_run_bundle = compose_run(metadata=metadata)
        return self.compose_run_bundle.start_doc

    def datum(self, doc):
        return doc

    def resource(self, doc):
        return doc

    def descriptor(self, doc):
        name = 'primary'
        data_keys = {'sum': {'shape': [], 'dtype': 'number'}}
        self.compose_descriptor_bundle = self.compose_run_bundle.compose_descriptor(
            name=name, data_keys=data_keys,
            object_names=None, configuration={}, hints=None)
        return self.compose_descriptor_bundle.descriptor_doc

    def event(self, doc):
        result = my_analysis_function(doc['data']['img'], self.factor)
        event_doc = self.compose_descriptor_bundle.compose_event(
            data={'sum': result},
            timestamps={'sum': time.time()},
            seq_num=doc['seq_num'])
        return event_doc

    def stop(self, doc):
        return self.compose_run_bundle.compose_stop()


from bluesky.callbacks import CallbackBase


class LiveProcessor(CallbackBase):
    def __init__(self, factor):
        self.factor = factor

    def __call__(self, name, doc):
        if name == 'start':
            return self.start(doc)
        if not self.applicable:
            return
        _, filled_doc = self.filler(name, doc)
        _, processed_doc = self.processor(name, filled_doc)
        print(processed_doc)
        processed_doc.pop('id', None)
        processed.insert(name, processed_doc)

    def start(self, doc):
        self.filler = Filler({"NPY_SEQ": NumpySeqHandler})
        self.applicable = is_applicable(doc)
        self.processor = Processor(factor=self.factor)
        _, processed_doc = self.processor('start', doc)
        processed.insert('start', processed_doc)


def process(uid, factor=1):
    print('processing', uid)
    gen = raw[uid].documents()
    # Pull off the first document, check that it is a 'start' document. (If it
    # is not something is *very* wrong.)
    name, start_doc = next(gen)
    assert name == 'start'
    # Check whether this process_callbacks is applicable to this run.
    if not is_applicable(start_doc):
        logger.info("Run %r is not applicable.", uid)
        return
    processor = Processor(factor=factor)
    # Push the start_doc through.
    _, processed_doc = processor('start', start_doc)
    processed.insert('start', processed_doc)
    filler = Filler({"NPY_SEQ": NumpySeqHandler})
    for name, doc in gen:
        _, filled_doc = filler(name, doc)
        _, processed_doc = processor(name, filled_doc)
        print('inserting')
        print(processed_doc)
        processed_doc.pop('id', None)
        processed.insert(name, processed_doc)


# ACQUISITION WITH LIVE PROCESSING

from bluesky import RunEngine
from ophyd.sim import img, motor
from bluesky.plans import scan

RE = RunEngine({})
RE.subscribe(raw.insert)
RE.subscribe(LiveProcessor(factor=1))
RE.subscribe(LiveProcessor(factor=3))

uid, = RE(scan([img], motor, -1, 1, 3))

# # RE-PROCESSING
#
# process_callbacks(uid, factor=10)
# process_callbacks(uid, factor=100)
#
# # ACCESS
#
# raw_header = raw[uid]  # db[uid]
#
# processed_headers = processed(raw_uid=uid)
# for processed_header in processed_headers:
#     print(processed_header.table())