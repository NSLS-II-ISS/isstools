from xas.trajectory import trajectory, trajectory_manager
import copy
from isstools.conversions import xray
import uuid
from subprocess import call


class Experiment:
    def __init__(self, name, comment, n_cycles, delay, element, edge, E0, Epreedge, kmax, t1, t2):

        self.run_parameters = {'name' : name,
                               'comment' : comment,
                               'n_cycles' : int(n_cycles),
                               'delay' : delay}

        self.traj_signature = {'element' : element,
                               'edge' : edge,
                               'E0' : float(E0),
                               'Epreedge' : float(Epreedge),
                               'kmax' : float(kmax),
                               't1' : float(t1),
                               't2' : float(t2)}






class TrajectoryStack:
    def __init__(self, hhm):

        self.most_recent = 0
        self.slots = [None]*8
        self.hhm = hhm
        self.traj_manager = trajectory_manager(hhm)
    #
    #
    # def check_if_exists(self, traj_signature):
    #     for slot in self.slots:
    #         if slot:
    #             if slot == traj_signature:
    #                 return True
    #     return False


    def set_traj(self, traj_signature, slot_number=1):
        # if exists, then initialize it on the controller
        if traj_signature:
            for traj_index, slot in enumerate(self.slots):
                if slot == traj_signature:
                    self.traj_manager.init(traj_index + 1)
                    return

            # if it does not exist, put it on the controller on the available slot
            for traj_index, slot in enumerate(self.slots):
                if slot is None:
                    self.slots[traj_index] = copy.deepcopy(traj_signature)
                    self.create_new_trajectory(traj_signature, traj_index)
                    return

            # if all slots are filled then FIFO
            self.slots[self.most_recent] = copy.deepcopy(traj_signature)
            self.create_new_trajectory(traj_signature, self.most_recent)
            self.update_most_recent()
        else:
            self.traj_manager.init(slot_number)



    def update_most_recent(self):
        if self.most_recent < 7: # numeration is from 0 to 7
            self.most_recent += 1
        else:
            self.most_recent = 0


    def create_new_trajectory(self, traj_signature, traj_index): # creates, saves, loads, and initializes trajectory with this signature

        traj_creator = trajectory(self.hhm)
        traj_creator.elem = traj_signature['element']
        traj_creator.edge = traj_signature['edge']
        traj_creator.e0 = str(traj_signature['E0'])

        preedge_lo = traj_signature['Epreedge']
        postedge_hi = xray.k2e(traj_signature['kmax'], traj_signature['E0']) - traj_signature['E0']

        traj_creator.define(edge_energy=traj_signature['E0'],
                            offsets=[preedge_lo, -30, 50, postedge_hi],
                            dsine_preedge_duration=traj_signature['t1'],
                            dsine_postedge_duration=traj_signature['t2'],
                            trajectory_type='Double Sine')
        traj_creator.interpolate()
        traj_creator.revert()


        fname = str(uuid.uuid4())[:8] + '.txt'
        fpath = self.hhm.traj_filepath + fname
        traj_creator.save(fpath)

        self.traj_manager.load(orig_file_name=fname,
                               new_file_path=traj_index + 1,
                               is_energy=True, offset=self.hhm.angle_offset.value)

        self.traj_manager.init(traj_index + 1)









    def batch_create_trajectories(self):
        for i in range(len(self.experiment_table)):
            d = self.experiment_table.iloc[i]
            traj = trajectory(self.hhm)
            kwargs = dict(
                edge_energy=d['Energy'],
                offsets=([d['pre-edge start'], d['pre-edge stop'],
                          d['post-edge stop'], xray.k2e(d['k-range'], d['Energy']) - d['Energy']]),
                trajectory_type='Double Sine',
                dsine_preedge_duration=d['time 1'],
                dsine_postedge_duration=d['time 2'],
            )
            print(kwargs)
            traj.define(**kwargs)

            # Add some more parameters manually:
            traj.elem = d['Element']
            traj.edge = d['Edge']
            traj.e0 = d['Energy']

            traj.interpolate()
            traj.revert()
            self.trajectories.append(traj)
            self.experiments.append(XASExperiment(definition=d))


    def save_trajectories(self):
        for ut in self.unique_trajectories:
            filename = os.path.join(self.trajectory_folder, 'trajectory_{}.txt'.format(str(uuid.uuid4())[:8]))
            self.trajectory_filenames.append(filename)
            print(f'Saving {filename}...')
            np.savetxt(filename, ut.energy_grid, fmt='%.6f',
                       header=f'element: {ut.elem}, edge: {ut.edge}, E0: {ut.e0}')
            call(['chmod', '666', filename])


    def load_trajectories(self):
        offset = self.hhm.angle_offset.value
        print(offset)
        for i, traj_file in enumerate(self.trajectory_filenames):
            self.trajectory_manager.load(os.path.basename(traj_file),i+1,is_energy=True, offset=offset )