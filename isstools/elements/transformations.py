def range_step_2_start_stop_nsteps(range, step):
    rel_start = -float(range)/2
    rel_stop = float(range) / 2
    num_steps = int(round(range / float(step))) + 1
    return rel_start, rel_stop, num_steps