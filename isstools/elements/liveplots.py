from bluesky.callbacks import LivePlot
import numpy as np

class NormPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, *args, **kwargs):
        # print(f'NormPlot *args: {args}')
        # print(f'NormPlot **kwargs: {kwargs}')
        super().__init__(result_name, x=motor, *args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.result_name = result_name

    def event(self, doc):
        doc = dict(doc)
        doc['data'] = dict(doc['data'])
        try:
            if self.den_name == '1':
                denominator = 1
            else:
                denominator = doc['data'][self.den_name]
            doc['data'][self.result_name] = doc['data'][self.num_name] / denominator
        except KeyError as ke:
            print(f"KeyError: {ke}")
        super().event(doc)


class XASPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, log = False, norm_name='1', *args, **kwargs):
        #print(f'NormPlot *args: {args}')
        #print(f'NormPlot **kwargs: {kwargs}')
        super().__init__(result_name, x=motor, *args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.result_name = result_name
        self.num_offset = None
        self.den_offset = None
        self.norm_name = norm_name
        self.log = log
        self.norm_name = norm_name

    def descriptor(self, doc):
        if self.num_name.startswith('apb'):
            num_offset_name = self.num_name.replace("_mean", "_offset")
            self.num_offset = doc["configuration"]['apb_ave']['data'][num_offset_name]
        else:
            self.num_offset = 0
        if self.den_name.startswith('apb'):
            den_offset_name = self.den_name.replace("_mean", "_offset")
            self.den_offset = doc["configuration"]['apb_ave']['data'][den_offset_name]
        else:
            self.den_offset = 0
        #print(f' Num off {self.num_offset}')
        #rint(f' Den off {self.den_offset}')


    def event(self, doc):
        #print(f' Numerator {self.num_name}')
        #print(f' Denominator {self.den_name}')
        doc = dict(doc)
        doc['data'] = dict(doc['data'])
        #print(doc['data'])
        try:
            if self.norm_name == '1':
                normalization = 1
            else:
                normalization = doc['data'][self.norm_name]


            if self.den_name == '1':
                denominator = 1
            else:
                denominator = np.abs(doc['data'][self.den_name]-self.den_offset)

            ratio = np.abs(doc['data'][self.num_name] - self.num_offset) / denominator / normalization
            if self.log:
                #TODO
                doc['data'][self.result_name] = np.log(ratio)
            else:
                doc['data'][self.result_name] = ratio

            #print(' Num {}'.format(doc['data'][self.num_name] - self.num_offset))
            #print(' Den {}'.format(denominator))
        except KeyError:
            print('Key error')
        #print(f"after normalizing:\n{doc['data']}")
        super().event(doc)

class XASPlotX(LivePlot):
    def __init__(self, num_name, den_name, encoder,result_name, motor, log=False, *args, **kwargs):
        # print(f'NormPlot *args: {args}')
        # print(f'NormPlot **kwargs: {kwargs}')
        super().__init__(result_name, x=motor, *args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.encoder = encoder
        self.result_name = result_name
        self.num_offset = None
        self.den_offset = None
        self.log = log

    def descriptor(self, doc):
        if self.num_name.startswith('apb'):
            num_offset_name = self.num_name.replace("_mean", "_offset")
            self.num_offset = doc["configuration"]['apb_ave']['data'][num_offset_name]
        else:
            self.num_offset = 0
        if self.den_name.startswith('apb'):
            den_offset_name = self.den_name.replace("_mean", "_offset")
            self.den_offset = doc["configuration"]['apb_ave']['data'][den_offset_name]
        else:
            self.den_offset = 0
        # print(f' Num off {self.num_offset}')
        # rint(f' Den off {self.den_offset}')

    def event(self, doc):
        # print(f' Numerator {self.num_name}')
        # print(f' Denominator {self.den_name}')
        doc = dict(doc)
        doc['data'] = dict(doc['data'])
        doc['data']['hhm_energy'] -=10000
        print(doc['data'])
        try:
            if self.den_name == '1':
                denominator = 1
            else:
                denominator = np.abs(doc['data'][self.den_name] - self.den_offset)

            ratio = np.abs(doc['data'][self.num_name] - self.num_offset) / denominator
            if self.log:
                # TODO
                doc['data'][self.result_name] = np.log(ratio)
            else:
                doc['data'][self.result_name] = ratio

            # print(' Num {}'.format(doc['data'][self.num_name] - self.num_offset))
            # print(' Den {}'.format(denominator))
        except KeyError:
            print('Key error')
        # print(f"after normalizing:\n{doc['data']}")
        super().event(doc)