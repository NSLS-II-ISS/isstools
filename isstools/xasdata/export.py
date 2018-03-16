import uuid
from databroker import Broker
import time
import numpy as np
import os
import os.path as op
import jsonschema
from event_model import DocumentNames, schemas


from pathlib import Path

# setup of objects to write to databroker


# 1. Need handlers for external data
# writing a file writer this is just an example
# writing a file handler is here
from databroker.assets.handlers import NpyHandler

# and define the writer to write to file and return some descriptor

# an example of writing to databroker 
# db is the databroker object
# db.mds is the metadatastore
def store_results_databroker(md, data, db, filepath, root=None):
    ''' Save results to a databroker instance.
        Takes a streamdoc instance.

        md : teh metadata
        data : dict
            keys:
                resource_kwargs
                datum_kwargs
                SPEC
        db : the databroker instance
        filename : the full filename of file you want to write
            needs to be an absolute path

        It is assumed everything here can be written with the same writer.
    '''
    # need the metadatastore of databroker
    #mds = db.mds  # metadatastore

    # This part creates all the documents
    # Store in databroker, make the documents
    start_doc = dict()
    # start_doc.update(attributes)
    # update the start doc with the metadata
    start_doc.update(**md)
    start_doc['time'] = time.time()
    start_doc['uid'] = str(uuid.uuid4())
    start_doc['plan_name'] = 'analysis'
    start_doc['save_timestamp'] = time.time()
    # need stream names
    start_doc['name'] = 'primary'

    # just make one descriptor and event document for now
    # initialize both event and descriptor
    descriptor_doc = dict()
    event_doc = dict()
    event_doc['data'] = dict()
    event_doc['timestamps'] = dict()
    descriptor_doc['data_keys'] = dict()
    descriptor_doc['time'] = time.time()
    descriptor_doc['uid'] = str(uuid.uuid4())
    descriptor_doc['run_start'] = start_doc['uid']
    descriptor_doc['name'] = 'primary'
    #descriptor_doc['object_keys'] = dict()

    event_doc['time'] = time.time()
    event_doc['uid'] = str(uuid.uuid4())
    event_doc['descriptor'] = descriptor_doc['uid']
    event_doc['seq_num'] = 1
    event_doc['filled'] = dict()



    # then parse remaining data
    for key, val in data.items():
        print("writing key {}".format(key))
        # guess descriptor from data
        # replace this with something to describe your data source
        descriptor_doc['data_keys'][key] = make_descriptor(val['data'], source="ISS-Analysis")
        # save to filestore
        # instantiate class with db.reg
        time_now = time.localtime()
        subpath = "/{:04}/{:02}/{:02}".format(time_now.tm_year,
                                              time_now.tm_mon,
                                              time_now.tm_mday)
        #writer = NpyWriter(filepath+subpath, db.reg, root=root)
        #new_id = writer.add_data(val)
        # should err here
        resource_path = val['resource_path']
        spec = val['SPEC']
        resource_kwargs = val.get('resource_kwargs', {})
        datum_kwargs = val.get('datum_kwargs', {})

        # todo : spit out asset resource docs
        resource = self.db_analysis.reg.insert_resource(val['SPEC'], resource_path,
                                            resource_kwargs,
                                            root=self._root)
        evl = self.db_analysis.reg.insert_datum(resource, uid, datum_kwargs)

        # at key give the identifier not the value
        event_doc['data'][key] = new_id
        event_doc['filled'][key] = False
        descriptor_doc['data_keys'][key].update(external="FILESTORE:")
        event_doc['timestamps'][key] = time.time()


    stop_doc = dict()
    stop_doc['time'] = time.time()
    stop_doc['uid'] = str(uuid.uuid4())
    stop_doc['run_start'] = start_doc['uid']
    stop_doc['exit_status'] = 'success'
    stop_doc['name'] = 'primary'

    # write the database results here to mongodb
    jsonschema.validate(start_doc, schemas[DocumentNames.start])
    jsonschema.validate(descriptor_doc, schemas[DocumentNames.descriptor])
    jsonschema.validate(event_doc, schemas[DocumentNames.event])
    jsonschema.validate(stop_doc, schemas[DocumentNames.stop])
    db.insert('start', start_doc)
    db.insert('descriptor', descriptor_doc)
    # TODO : spit out asset docs
    db.insert('event', event_doc)
    db.insert('stop', stop_doc)



# quick dummy script to make a descriptor
def make_descriptor(val, source=None):
    ''' make a descriptor from value through guessing.'''
    if source is None:
        raise ValueError("Error source must be defined")
    shape = ()
    if np.isscalar(val):
        dtype = 'number'
    elif isinstance(val, np.ndarray):
        dtype = 'array'
        shape = val.shape
    elif isinstance(val, list):
        dtype = 'list'
        shape = (len(val),)
    elif isinstance(val, dict):
        dtype = 'dict'
    else:
        dtype = 'unknown'

    return dict(dtype=dtype, shape=shape, source=source)
