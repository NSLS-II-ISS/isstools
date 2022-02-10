from bluesky.callbacks import LivePlot
import numpy as np

class NormPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, *args, **kwargs):
        super().__init__(result_name, x=motor, *args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.result_name = result_name
        # self.start_figure_func = start_figure_func
        # self.stop_figure_func = stop_figure_func
        # self.start_figure_func()

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

    # def start(self, doc):
    #     result = super().start(doc)
    #     if start_figure_func is not None:
    #         self.start_figure_func()

    # def stop(self, doc):
    #     if stop_figure_func is not None:
    #         self.stop_figure_func()
    #     return super().stop(doc)


class XASPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, log = False, norm_name='1', *args, **kwargs):
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



    def event(self, doc):
        doc = dict(doc)
        doc['data'] = dict(doc['data'])
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

        except KeyError:
            print('Key error')
        super().event(doc)
