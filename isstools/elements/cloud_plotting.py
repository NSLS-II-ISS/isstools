from isstools.xasproject.xasproject import XASDataSet
from xas.file_io import load_binned_df_from_file
import numpy as np
from matplotlib import pyplot as plt

def generate_output_figures(filepath, imagepath=None, t_flag=True, f_flag=True, r_flag=True):
    plt.ioff()
    df, header = load_binned_df_from_file(filepath)
    df = df.sort_values('energy')

    mu_t = np.array(np.log(df['i0']/df['it']))
    mu_f = np.array(df['iff']/df['i0'])
    mu_r = np.array(np.log(df['it']/df['ir']))

    ds_t = XASDataSet(name=filepath, md={}, energy=df['energy'], mu=mu_t, filename=filepath, datatype='experiment')
    ds_f = XASDataSet(name=filepath, md={}, energy=df['energy'], mu=mu_f, filename=filepath, datatype='experiment')
    ds_r = XASDataSet(name=filepath, md={}, energy=df['energy'], mu=mu_r, filename=filepath, datatype='experiment')

    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(8, 9))

    fig.set_tight_layout(True)
    legend = []
    if t_flag:
        plot_xas_in_E(ds_t, ax1, color='b')
        plot_xas_in_K(ds_t, ax2, color='b')
        legend.append('Transmission')

    if f_flag:
        plot_xas_in_E(ds_f, ax3, color='r')
        plot_xas_in_K(ds_f, ax4, color='r')
        legend.append('Fluorescence')

    if r_flag:
        plot_xas_in_E(ds_r, ax5, color='k')
        plot_xas_in_K(ds_r, ax6, color='k')
        legend.append('Reference')

    ax1.legend(legend)

    ax1.set_xlabel('E, eV')
    ax1.set_ylabel('norm/flat mu')
    ax3.set_xlabel('E, eV')
    ax3.set_ylabel('norm/flat mu')
    ax5.set_xlabel('E, eV')
    ax5.set_ylabel('norm/flat mu')

    ax2.set_xlabel('k, A$^{-1}$')
    ax2.set_ylabel('$\chi$(k) * k$^{2}$')
    ax4.set_xlabel('k, A$^{-1}$')
    ax4.set_ylabel('$\chi$(k) * k$^{2}$')
    ax5.set_xlabel('k, A$^{-1}$')
    ax6.set_ylabel('$\chi$(k) * k$^{2}$')

    # plt.tight_layout()
    if imagepath:
        plt.savefig(imagepath, dpi=300)
    plt.ion()
    plt.close(fig)



def plot_xas_in_E(ds, ax, color):
    ds.normalize_force()
    # ds.extract_chi_force()
    # ds.extract_ft()
    energy = ds.energy
    ax.plot(energy, ds.flat, color=color)
    # ax.plot(energy, ds.mu, color=color)


def plot_xas_in_K(ds, ax, color):
    # ds.normalize_force()
    ds.extract_chi_force()
    # ds.extract_ft()
    # energy = ds.energy
    # ax.plot(energy, ds.flat)
    ax.plot(ds.k, ds.chi * ds.k**2, color=color)
