import numpy as np


def move_to_sample(zero_x, zero_y, delta_first_holder_x, delta_first_holder_y, index_stack, index_holder, index_sample):
    delta_sample_x = 15
    delta_stack_x = 100
    delta_holder_y = 16
    delta_stack_y = 100

    disp_stack_x = index_stack - 1 - (np.floor((index_stack - 1) / 3)) * 3
    disp_stack_y = np.floor((index_stack - 1) / 3)

    Giant_x = zero_x + delta_first_holder_x + delta_sample_x * index_sample + delta_stack_x * disp_stack_x
    Giant_y = zero_y + delta_first_holder_y - (index_holder - 1) * delta_holder_y + delta_stack_y * disp_stack_y

    return Giant_x, Giant_y