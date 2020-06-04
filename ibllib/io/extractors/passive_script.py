"""
Get passive CW session and data.

STEPS:
- Load fixture data
- Find spacer (still do convolution?) + check number found
- Cut out part about ephysCW
- Get number of TTL switch (f2ttl, audio, valve) within each spacer
- Associate TTL found for each stim type + check number found
- Package and output data (alf format?)
"""
# Author: Olivier W, Gaelle C
import alf.io
from oneibl.one import ONE
from pathlib import Path
import numpy as np
import json
# plot for debug
# from ibllib.plots import squares
# import matplotlib.pyplot as plt

import ibllib.io.extractors.passive as passive

import ibllib.io.raw_data_loaders as rawio
from ibllib.io.extractors import ephys_fpga

# hardcoded var
FRAME_FS = 60  # Sampling freq of the ipad screen, in Hertz
FS_FPGA = 30000  # Sampling freq of the neural recording system screen, in Hertz

# load data
one = ONE()
dataset_types = ['_spikeglx_sync.times',
                 '_spikeglx_sync.channels',
                 '_spikeglx_sync.polarities',
                 '_iblrig_RFMapStim.raw',
                 '_iblrig_stimPositionScreen.raw',
                 '_iblrig_syncSquareUpdate.raw',
                 'ephysData.raw.meta',
                 '_iblrig_taskSettings.raw'
                 ]

eid = one.search(subject='CSH_ZAD_022', date_range='2020-05-24', number=1)[0]
local_paths = one.load(eid, dataset_types=dataset_types, download_only=True)

session_path = alf.io.get_session_path(local_paths[0])

# load session fixtures
settings = rawio.load_settings(session_path)
ses_nb = settings['SESSION_ORDER'][settings['SESSION_IDX']]
path_fixtures = Path(ephys_fpga.__file__).parent.joinpath('ephys_sessions')
pcs = np.load(path_fixtures.joinpath(f'session_{ses_nb}_passive_pcs.npy'))
delays = np.load(path_fixtures.joinpath(f'session_{ses_nb}_passive_stimDelays.npy'))
ids = np.load(path_fixtures.joinpath(f'session_{ses_nb}_passive_stimIDs.npy'))

# load general metadata
json_file = path_fixtures.joinpath('passive_stim_meta.json')
with open(json_file, 'r') as f:
    meta = json.load(f)

# load ephys sync pulses
sync, sync_map = ephys_fpga._get_main_probe_sync(session_path, bin_exists=False)
fpga_sync = ephys_fpga._get_sync_fronts(sync, sync_map['frame2ttl'])

# load Frame2ttl / audio / valve signal
fttl = ephys_fpga._get_sync_fronts(sync, sync_map['frame2ttl'])
audio = ephys_fpga._get_sync_fronts(sync, sync_map['audio'])
valve = ephys_fpga._get_sync_fronts(sync, sync_map['bpod'])
# todo check that bpod does not output any other signal than valve in this task protocol

# load stimulus sequence
stim_order = np.array(meta['STIM_ORDER'])

# load RF matrix and reshape
RF_file = Path.joinpath(session_path, 'raw_passive_data', '_iblrig_RFMapStim.raw.bin')
frames = passive.reshape_RF(RF_file=RF_file, meta=meta)  # todo add n expected frame

# truncate f2ttl signal so as to contain only what comes after ephysCW
t_end_ephys = passive.ephysCW_end(session_path=session_path)
fttl_trunk = dict()
fttl_trunk['times'] = fttl['times'][fttl['times'] > t_end_ephys]
fttl_trunk['polarities'] = fttl['polarities'][fttl['times'] > t_end_ephys]

# load and get spacer information, do convolution to find spacer timestamps
ttl_signal = fttl_trunk['times']
spacer_template = np.array(meta['VISUAL_STIM_0']['ttl_frame_nums'], dtype=np.float32) / FRAME_FS
jitter = 3 / FRAME_FS  # allow for 3 screen refresh as jitter
t_quiet = meta['VISUAL_STIM_0']['delay_around']
spacer_times, conv_dttl = passive.get_spacer_times(
    spacer_template=spacer_template, jitter=jitter,
    ttl_signal=ttl_signal, t_quiet=t_quiet)

# Check correct number of spacer is found
indx_0 = np.where(stim_order == 0)  # Hardcoded 0
n_exp_spacer = np.size(indx_0)
if n_exp_spacer != np.size(spacer_times) / 2:
    raise ValueError(f'The number of expected spacer ({n_exp_spacer}) '
                     f'is different than the one found on the raw '
                     f'trace ({np.size(spacer_times)/2})')

# split ids into relevant HW categories
gabor_id = [s for s in ids if 'G' in s]
valve_id = [s for s in ids if 'V' in s]
matched = ['T', 'N']
sound_id = [z for z in ids if z in matched]

# Test correct number is found in metadata (hardcoded from protocol)
# Todo is this necessary here? This should be done upon creation of the npy file
len_g_pr = 20 + 20 * 4 * 2
if len_g_pr != len(gabor_id):
    raise ValueError("N Gabor stimulus in metadata incorrect")
len_v_pr = 40
if len_v_pr != len(valve_id):
    raise ValueError("N Valve stimulus in metadata incorrect")
len_s_pr = 40 * 2
if len_s_pr != len(sound_id):
    raise ValueError("N Sound stimulus in metadata incorrect")
