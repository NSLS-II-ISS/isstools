import numpy as np
import bluesky.plan_stubs as bps


delta_stack_x = 108.0 
delta_stack_y = 132.4





# def move_to_sample(zero_x, zero_y, delta_first_holder_x, delta_first_holder_y, index_stack, index_holder, index_sample):
#     delta_sample_x = 15 # 28.4
#     delta_stack_x = 109.2 # 101.55 + 7.65
#     delta_holder_y = 16.14
#     delta_stack_y = 133
#
#     disp_stack_x = index_stack - 1 - (np.floor((index_stack - 1) / 3)) * 3
#     disp_stack_y = np.floor((index_stack - 1) / 3)
#
#     Giant_x = zero_x + delta_first_holder_x + delta_sample_x * index_sample + delta_stack_x * disp_stack_x
#     Giant_y = zero_y + delta_first_holder_y - (index_holder - 1) * delta_holder_y + delta_stack_y * disp_stack_y
#
#     return Giant_x, Giant_y
#
#
# def shift_stage_to_zero(cur_x_pix, cur_y_pix, zero_x_pix, zero_y_pix, calib=10.957):
#     delta_x = -(zero_x_pix - cur_x_pix) / calib
#     delta_y = (zero_y_pix - cur_y_pix) / calib
#     return delta_x, delta_y



class SamplePositioner:

    def __init__(self,
                 RE,
                 sample_stage,
                 stage_park_x,
                 stage_park_y,
                 delta_first_holder_x=0,
                 delta_first_holder_y=0):

        '''
        :param zero_x: zero position of the giant stage x
        :param zero_y: zero position of the giant stage y
        :param delta_first_holder_x: relative x move from the zero position to the first qr-code in the first stack
        :param delta_first_holder_y: relative y move from the zero position to the first qr-code in the first stack
        :param RE: RE
        :param sample_stage: giant stage handle
        '''
        self.RE = RE
        self.sample_stage = sample_stage

        # this comes from our calibration
        self.stage_park_x = stage_park_x
        self.stage_park_y = stage_park_y
        self.delta_first_holder_x = delta_first_holder_x
        self.delta_first_holder_y = delta_first_holder_y

        # distances between stacks
        self.delta_stack_x = delta_stack_x
        self.delta_stack_y = delta_stack_y

        self.n_stacks = 9
        self.n_holders = 4

        self.delta_holder = {'type_1' : {'x' : 14.9, 'y': 17.5},
                             'type_2' : {'x' : 1, 'y': 1}}

    def goto_park(self):
        self.RE(bps.mv(self.sample_stage.x, self.stage_park_x))
        self.RE(bps.mv(self.sample_stage.y, self.stage_park_y))


    def goto_holder(self, index_stack, index_holder):
        self.goto_sample(index_stack, index_holder, 1)


    def goto_sample(self, index_stack, index_holder, index_sample, holder_type=1):
        giant_x, giant_y = self.get_sample_position(index_stack, index_holder, index_sample, holder_type=holder_type)

        self.RE(bps.mv(self.sample_stage.x, giant_x))
        self.RE(bps.mv(self.sample_stage.y, giant_y))



    def get_sample_position(self, index_stack, index_holder, index_sample, holder_type=1):

        if holder_type == 1:
            assert index_sample < 5, 'sample index must be between 1 and 4'
            delta_holder_x = self.delta_holder['type_1']['x']  # shift to the next sample wihtin the same holder
            delta_holder_y = self.delta_holder['type_1']['y']
        else:  # other types of sample holders
            pass

        print(f'delta_holder_x = {delta_holder_x}')

        disp_stack_x = index_stack - 1 - (np.floor((index_stack - 1) / 3)) * 3
        disp_stack_y = np.floor((index_stack - 1) / 3)

        giant_x = (self.stage_park_x +
                   self.delta_first_holder_x +
                   delta_holder_x * (index_sample - 1) +
                   self.delta_stack_x * disp_stack_x)
        giant_y = (self.stage_park_y +
                   self.delta_first_holder_y -
                   (index_holder - 1) * delta_holder_y +
                   self.delta_stack_y * disp_stack_y)

        return np.round(giant_x, 3), np.round(giant_y, 3)


    def goto_xy(self, x, y):
        self.RE(bps.mv(self.sample_stage.x, x))
        self.RE(bps.mv(self.sample_stage.y, y))


    # def get_stack_holder_list(self):
    #     self.stack_holder_list = []
    #     for i in range(1, 10):
    #         for j in range(1, 5):
    #             self.stack_holder_list.append([i, j])
