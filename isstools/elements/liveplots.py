from bluesky.callbacks import LivePlot


class NormPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, motor, *args, **kwargs):
        print(f'NormPlot *args: {args}')
        print(f'NormPlot **kwargs: {kwargs}')
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
