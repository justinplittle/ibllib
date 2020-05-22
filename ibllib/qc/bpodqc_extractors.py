# TODO: Fix new extractor signature/saving files - Make class?
import logging
import os
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd
from scipy import interpolate
from pkg_resources import parse_version

import ibllib.io.raw_data_loaders as raw
from ibllib.io.extractors.training_trials import (get_choice,
                                                  get_feedback_times,
                                                  get_feedbackType,
                                                  get_goCueOnset_times,
                                                  get_goCueTrigger_times,
                                                  get_intervals,
                                                  get_port_events,
                                                  get_response_times,
                                                  get_rewardVolume,
                                                  get_stimOn_times,
                                                  get_stimOnTrigger_times)
from ibllib.io.extractors.training_wheel import get_wheel_position
from ibllib.qc.oneutils import uuid_to_path
from oneibl.one import ONE

log = logging.getLogger("ibllib")


def get_bpod_fronts(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    BNC1_fronts = np.array([[np.nan, np.nan]])
    BNC2_fronts = np.array([[np.nan, np.nan]])
    for tr in data:
        BNC1_fronts = np.append(
            BNC1_fronts,
            np.array(
                [
                    [x, 1]
                    for x in tr["behavior_data"]["Events timestamps"].get("BNC1High", [np.nan])
                ]
            ),
            axis=0,
        )
        BNC1_fronts = np.append(
            BNC1_fronts,
            np.array(
                [
                    [x, -1]
                    for x in tr["behavior_data"]["Events timestamps"].get("BNC1Low", [np.nan])
                ]
            ),
            axis=0,
        )
        BNC2_fronts = np.append(
            BNC2_fronts,
            np.array(
                [
                    [x, 1]
                    for x in tr["behavior_data"]["Events timestamps"].get("BNC2High", [np.nan])
                ]
            ),
            axis=0,
        )
        BNC2_fronts = np.append(
            BNC2_fronts,
            np.array(
                [
                    [x, -1]
                    for x in tr["behavior_data"]["Events timestamps"].get("BNC2Low", [np.nan])
                ]
            ),
            axis=0,
        )

    BNC1_fronts = BNC1_fronts[1:, :]
    BNC1_fronts = BNC1_fronts[BNC1_fronts[:, 0].argsort()]
    BNC2_fronts = BNC2_fronts[1:, :]
    BNC2_fronts = BNC2_fronts[BNC2_fronts[:, 0].argsort()]

    BNC1 = {"times": BNC1_fronts[:, 0], "polarities": BNC1_fronts[:, 1]}
    BNC2 = {"times": BNC2_fronts[:, 0], "polarities": BNC2_fronts[:, 1]}

    return [BNC1, BNC2]


# --------------------------------------------------------------------------- #
# @uuid_to_path(dl=True)
def get_trial_type(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    trial_type = []
    for tr in data:
        if ~np.isnan(tr["behavior_data"]["States timestamps"]["reward"][0][0]):
            trial_type.append(1)
        elif ~np.isnan(tr["behavior_data"]["States timestamps"]["error"][0][0]):
            trial_type.append(-1)
        elif ~np.isnan(tr["behavior_data"]["States timestamps"]["no_go"][0][0]):
            trial_type.append(0)
        else:
            log.warning("Trial is not in set {-1, 0, 1}, appending NaN to trialType")
            trial_type.append(np.nan)

    trial_type = np.array(trial_type)

    if raw.save_bool(save, "_ibl_trials.type.npy"):
        lpath = os.path.join(session_path, "alf", "_ibl_trials.type.npy")
        np.save(lpath, trial_type)

    return trial_type


# @uuid_to_path(dl=True)
def get_itiIn_times(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    if not parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("5.0.0"):
        return np.ones(len(data)) * np.nan

    itiIn_times = np.array(
        [tr["behavior_data"]["States timestamps"]["exit_state"][0][0] for tr in data]
    )

    if raw.save_bool(save, "_ibl_trials.itiIn_times.npy"):
        lpath = os.path.join(session_path, "alf", "_ibl_trials.itiIn_times.npy")
        np.save(lpath, itiIn_times)

    return itiIn_times


# @uuid_to_path(dl=True)
def get_stimFreezeTrigger_times(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    if not parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("6.2.5"):
        return np.ones(len(data)) * np.nan

    freeze_reward = np.array(
        [
            True
            if np.all(~np.isnan(tr["behavior_data"]["States timestamps"]["freeze_reward"][0]))
            else False
            for tr in data
        ]
    )
    freeze_error = np.array(
        [
            True
            if np.all(~np.isnan(tr["behavior_data"]["States timestamps"]["freeze_error"][0]))
            else False
            for tr in data
        ]
    )
    no_go = np.array(
        [
            True
            if np.all(~np.isnan(tr["behavior_data"]["States timestamps"]["no_go"][0]))
            else False
            for tr in data
        ]
    )
    assert np.sum(freeze_error) + np.sum(freeze_reward) + np.sum(no_go) == len(data)

    stimFreezeTrigger = np.array([])
    for r, e, n, tr in zip(freeze_reward, freeze_error, no_go, data):
        if n:
            stimFreezeTrigger = np.append(stimFreezeTrigger, np.nan)
            continue
        state = "freeze_reward" if r else "freeze_error"
        stimFreezeTrigger = np.append(
            stimFreezeTrigger, tr["behavior_data"]["States timestamps"][state][0][0]
        )

    if raw.save_bool(save, "_ibl_trials.stimFreeze_times.npy"):
        lpath = os.path.join(session_path, "alf", "_ibl_trials.stimFreeze_times.npy")
        np.save(lpath, stimFreezeTrigger)

    return stimFreezeTrigger


# @uuid_to_path(dl=True)
def get_stimOffTrigger_times(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    if parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("6.2.5"):
        stim_off_trigger_state = "hide_stim"
    elif parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("5.0.0"):
        stim_off_trigger_state = "exit_state"
    else:
        stim_off_trigger_state = "trial_start"

    stimOffTrigger_times = np.array(
        [tr["behavior_data"]["States timestamps"][stim_off_trigger_state][0][0] for tr in data]
    )
    no_goTrigger_times = np.array(
        [tr["behavior_data"]["States timestamps"]["no_go"][0][0] for tr in data]
    )
    # Stim off trigs are either in their own state or in the no_go state if the mouse did not move
    assert all(~np.isnan(no_goTrigger_times) == np.isnan(stimOffTrigger_times))
    stimOffTrigger_times[~np.isnan(no_goTrigger_times)] = no_goTrigger_times[
        ~np.isnan(no_goTrigger_times)
    ]

    if raw.save_bool(save, "_ibl_trials.stimOffTrigger_times.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.stimOffTrigger_times.npy")
        np.save(lpath, stimOffTrigger_times)

    return stimOffTrigger_times


# @uuid_to_path(dl=True)
def get_stimOff_times_from_state(session_path, save=False, data=False, settings=False):
    """ Will return NaN is trigger state == 0.1 secs
    """

    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    if parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("6.2.5"):
        stim_off_trigger_state = "hide_stim"
    elif parse_version(settings["IBLRIG_VERSION_TAG"]) >= parse_version("5.0.0"):
        stim_off_trigger_state = "exit_state"
    else:
        stim_off_trigger_state = "trial_start"

    stim_off_trigger_state_values = np.array(
        [tr["behavior_data"]["States timestamps"][stim_off_trigger_state][0] for tr in data]
    )
    stimOff_times = np.array([])
    for s in stim_off_trigger_state_values:
        x = s[0] - s[1]
        if np.isnan(x) or np.abs(x) > 0.0999:
            stimOff_times = np.append(stimOff_times, np.nan)
        else:
            stimOff_times = np.append(stimOff_times, s[1])

    if raw.save_bool(save, "_ibl_trials.stimOff_times.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.stimOff_times.npy")
        np.save(lpath, stimOff_times)

    return stimOff_times


# @uuid_to_path(dl=True)
def get_stimOnOffFreeze_times_from_BNC1(session_path, save=False, data=False, settings=False):
    """Get stim onset offset and freeze using the FPGA specifications"""
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    choice = get_choice(session_path, data=data, settings=settings)
    f2TTL = [get_port_events(tr, name="BNC1") for tr in data]
    stimOn_times = np.array([])
    stimOff_times = np.array([])
    stimFreeze_times = np.array([])

    for tr in f2TTL:
        if tr and len(tr) >= 2:
            # 2nd order criteria:
            # stimOn -> Closest one to stimOnTrigger?
            # stimOff -> Closest one to stimOffTrigger?
            # stimFreeze -> Closest one to stimFreezeTrigger?
            stimOn_times = np.append(stimOn_times, tr[0])
            stimOff_times = np.append(stimOff_times, tr[-1])
            stimFreeze_times = np.append(stimFreeze_times, tr[-2])
        else:
            stimOn_times = np.append(stimOn_times, np.nan)
            stimOff_times = np.append(stimOff_times, np.nan)
            stimFreeze_times = np.append(stimFreeze_times, np.nan)

    # In no_go trials no stimFreeze happens jsut stim Off
    stimFreeze_times[choice == 0] = np.nan

    if raw.save_bool(save, "_ibl_trials.stimOn_times.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.stimOn_times.npy")
        np.save(lpath, stimOn_times)
    if raw.save_bool(save, "_ibl_trials.stimOff_times.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.stimOff_times.npy")
        np.save(lpath, stimOff_times)
    if raw.save_bool(save, "_ibl_trials.stimFreeze_times.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.stimFreeze_times.npy")
        np.save(lpath, stimFreeze_times)

    return stimOn_times, stimOff_times, stimFreeze_times


# TODO: UNUSED!! USE IT!
def get_bonsai_screen_data(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})
    path = Path(session_path).joinpath("raw_behavior_data", "_iblrig_stimPositionScreen.raw.csv")
    screen_data = pd.read_csv(path, sep=" ", header=None)

    return screen_data


# TODO: UNUSED!! USE IT!
def get_bonsai_sync_square_update_times(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    path = Path(session_path).joinpath("raw_behavior_data", "_iblrig_syncSquareUpdate.raw.csv")
    if path.exists():
        sync_square_update_times = pd.read_csv(path, sep=",", header=None)
        return sync_square_update_times

    return


# @uuid_to_path(dl=True)
def get_errorCueTrigger_times(session_path, save=False, data=False, settings=False):
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})

    errorCueTrigger_times = np.zeros(len(data)) * np.nan

    for i, tr in enumerate(data):
        nogo = tr["behavior_data"]["States timestamps"]["no_go"][0][0]
        error = tr["behavior_data"]["States timestamps"]["error"][0][0]
        if np.all(~np.isnan(nogo)):
            errorCueTrigger_times[i] = nogo
        elif np.all(~np.isnan(error)):
            errorCueTrigger_times[i] = error

    return errorCueTrigger_times


# @uuid_to_path(dl=True)
def _get_trimmed_data_from_pregenerated_files(
    session_path, save=False, data=False, settings=False
):
    """Extracts positions, contrasts, quiescent delay, stimulus phase and probability left
    from pregenerated session files.
    Optional: saves alf contrastLR and probabilityLeft npy files"""
    if not data:
        data = raw.load_data(session_path)
    if not settings:
        settings = raw.load_settings(session_path)
    if settings is None:
        settings = {"IBLRIG_VERSION_TAG": "100.0.0"}
    elif settings["IBLRIG_VERSION_TAG"] == "":
        settings.update({"IBLRIG_VERSION_TAG": "100.0.0"})
    num = settings.get("PRELOADED_SESSION_NUM", None)
    if num is None:
        num = settings.get("PREGENERATED_SESSION_NUM", None)
    if num is None:
        fn = settings.get("SESSION_LOADED_FILE_PATH", None)
        fn = PureWindowsPath(fn).name
        num = "".join([d for d in fn if d.isdigit()])
        if num == "":
            raise ValueError("Can't extract left probability behaviour.")
    # Load the pregenerated file
    sessions_folder = Path(raw.__file__).parent.joinpath("extractors", "ephys_sessions")
    fname = f"session_{num}_ephys_pcqs.npy"
    pcqsp = np.load(sessions_folder.joinpath(fname))
    pos = pcqsp[:, 0]
    con = pcqsp[:, 1]
    pos = pos[: len(data)]
    con = con[: len(data)]
    contrastRight = con.copy()
    contrastLeft = con.copy()
    contrastRight[pos < 0] = np.nan
    contrastLeft[pos > 0] = np.nan
    qui = pcqsp[:, 2]
    qui = qui[: len(data)]
    phase = pcqsp[:, 3]
    phase = phase[: len(data)]
    pLeft = pcqsp[:, 4]
    pLeft = pLeft[: len(data)]

    if raw.save_bool(save, "_ibl_trials.contrastLeft.npy"):
        lpath = os.path.join(session_path, "alf", "_ibl_trials.contrastLeft.npy")
        np.save(lpath, contrastLeft)

    if raw.save_bool(save, "_ibl_trials.contrastRight.npy"):
        rpath = os.path.join(session_path, "alf", "_ibl_trials.contrastRight.npy")
        np.save(rpath, contrastRight)

    if raw.save_bool(save, "_ibl_trials.probabilityLeft.npy"):
        lpath = Path(session_path).joinpath("alf", "_ibl_trials.probabilityLeft.npy")
        np.save(lpath, pLeft)

    return {
        "position": pos,
        "contrast": con,
        "quiescence": qui,
        "phase": phase,
        "prob_left": pLeft,
    }


@uuid_to_path(dl=True)
def extract_bpod_trial_table(session_path, raw_data=None, raw_settings=None, fpga_time=False):
    """Extracts and loads ephys sessions from bpod data"""
    log.info(f"Extracting session: {session_path}")
    data = raw_data or raw.load_data(session_path)
    settings = raw_settings or raw.load_settings(session_path)
    stimOn_times, stimOff_times, stimFreeze_times = get_stimOnOffFreeze_times_from_BNC1(
        session_path, save=False, data=data, settings=settings,
    )

    out = {
        "position": None,
        "contrast": None,
        "quiescence": None,
        "phase": None,
        "prob_left": None,
        "choice": get_choice(session_path, save=False, data=data, settings=settings),
        "feedbackType": get_feedbackType(session_path, save=False, data=data, settings=settings),
        "correct": None,
        "outcome": None,
        "intervals": get_intervals(session_path, save=False, data=data, settings=settings),
        "stimOnTrigger_times": get_stimOnTrigger_times(
            session_path, save=False, data=data, settings=settings
        ),
        "stimOn_times": stimOn_times,
        "stimOn_times_training": get_stimOn_times(
            session_path, save=False, data=data, settings=settings
        ),
        "stimOffTrigger_times": get_stimOffTrigger_times(
            session_path, save=False, data=data, settings=settings
        ),
        "stimOff_times": stimOff_times,
        "stimOff_times_from_state": get_stimOff_times_from_state(
            session_path, save=False, data=data, settings=settings
        ),
        "stimFreezeTrigger_times": get_stimFreezeTrigger_times(
            session_path, save=False, data=data, settings=settings
        ),
        "stimFreeze_times": stimFreeze_times,
        "goCueTrigger_times": get_goCueTrigger_times(
            session_path, save=False, data=data, settings=settings
        ),
        "goCue_times": get_goCueOnset_times(
            session_path, save=False, data=data, settings=settings
        ),
        "errorCueTrigger_times": get_errorCueTrigger_times(
            session_path, save=False, data=data, settings=settings
        ),
        "errorCue_times": None,
        "valveOpen_times": None,
        "rewardVolume": get_rewardVolume(session_path, save=False, data=data, settings=settings),
        "response_times": get_response_times(
            session_path, save=False, data=data, settings=settings
        ),
        "feedback_times": get_feedback_times(
            session_path, save=False, data=data, settings=settings
        ),
        "itiIn_times": get_itiIn_times(session_path, save=False, data=data, settings=settings),
        "intervals_0": None,
        "intervals_1": None,
        # XXX: First (all?) audio input times for each trial for load_audio_pre_trial metric
        # XXX: f2ttl times in trials for load_stimulus_move_before_goCue
    }
    out.update(
        _get_trimmed_data_from_pregenerated_files(
            session_path, save=False, data=data, settings=settings
        )
    )
    # get valve_time and errorCue_times from feedback_times
    correct = np.sign(out["position"]) + np.sign(out["choice"]) == 0
    errorCue_times = out["feedback_times"].copy()
    valveOpen_times = out["feedback_times"].copy()
    errorCue_times[correct] = np.nan
    valveOpen_times[~correct] = np.nan
    out.update(
        {"errorCue_times": errorCue_times, "valveOpen_times": valveOpen_times, "correct": correct}
    )
    # split intervals
    out["intervals_0"] = out["intervals"][:, 0]
    out["intervals_1"] = out["intervals"][:, 1]
    _ = out.pop("intervals")
    out["outcome"] = out["feedbackType"].copy()
    out["outcome"][out["choice"] == 0] = 0
    # Optional convert times to FPGA clock
    if fpga_time:
        bpod2fpga = get_bpod2fpga_times_func(session_path)
        for k in out:
            if "_times" in k or "intervals" in k:
                out[k] = bpod2fpga(out[k])
    return out


# @uuid_to_path(dl=True)
def get_bpod2fpga_times_func(session_path):
    session_path = Path(session_path)

    # Load bpod intervals
    data = raw.load_data(session_path)
    settings = raw.load_settings(session_path)
    bpod_intervals = get_intervals(session_path, save=False, data=data, settings=settings)
    # Load _ibl_trials.intervals.npy
    fpath = session_path / "alf" / "_ibl_trials.intervals.npy"
    if fpath.exists():
        fpga_intervals = np.load(fpath)
    else:
        log.warning(f"tirals.intervals datasetType not found in {fpath}")
        return
    # align
    bpod_tstarts, fpga_tstarts = raw.sync_trials_robust(bpod_intervals[:, 0], fpga_intervals[:, 0])
    # Generate interp func
    bpod2fpga = interpolate.interp1d(bpod_tstarts, fpga_tstarts, fill_value="extrapolate")

    return bpod2fpga


class BpodQCExtractor(object):
    def __init__(self, session_path, lazy=True):
        self.session_path = session_path
        self.load_raw_data()
        if not lazy:
            self.extract_trial_data()

    def load_raw_data(self):
        self.raw_data = raw.load_data(self.session_path)
        self.details = raw.load_settings(self.session_path)
        self.BNC1, self.BNC2 = get_bpod_fronts(
            self.session_path, data=self.raw_data, settings=self.details
        )
        self.wheel_data = get_wheel_position(self.session_path, bp_data=self.raw_data)
        assert np.all(np.diff(self.wheel_data["re_ts"]) > 0)

    def extract_trial_data(self):
        self.trial_data = extract_bpod_trial_table(
            self.session_path, raw_data=self.raw_data, raw_settings=self.details, fpga_time=False
        )


if __name__ == "__main__":
    # from ibllib.qc.bpodqc import *
    subj_path = "/home/nico/Projects/IBL/github/iblapps/scratch/TestSubjects/"
    # Guido's 3B
    gsession_path = subj_path + "_iblrig_test_mouse/2020-02-11/001"
    test_db_eid = "b1c968ad-4874-468d-b2e4-5ffa9b9964e9"
    one = ONE(base_url='https://test.alyx.internationalbrainlab.org', username='test_user',
              password='TapetesBloc18')
    sesspath = one.path_from_eid(test_db_eid)
    bla = BpodQCExtractor(sesspath)
    # Alex's 3A
    asession_path = subj_path + "_iblrig_test_mouse/2020-02-18/006"
    a2session_path = subj_path + "_iblrig_test_mouse/2020-02-21/011"
    eid = "af74b29d-a671-4c22-a5e8-1e3d27e362f3"
    session_path = gsession_path
    # bpod = extract_bpod_trial_table(session_path)
    # fpgaqc_frame = _qc_from_path(session_path, display=False)
    # bpodqc_frame = get_bpodqc_frame(session_path)

    # bla = [(
    # k, all(fpgaqc_frame[k] == bpodqc_frame[k])) for k in fpgaqc_frame if k in bpodqc_frame
    # ]

    # count_qc_failures(session_path)
    # plt.ion()
    # f, ax = plt.subplots()
    # plot_bpod_session(session_path, ax=ax)

    # eid = "a71175be-d1fd-47a3-aa93-b830ea3634a1"
    # plot_session_trigger_response_diffs(eid)
    # one.search_terms()
    # eids, dets = one.search(task_protocol="ephysChoiceWorld6.2.5", lab="mainenlab", details=True)
    one = ONE(printout=False)
    labs = one.list(None, "lab")
    # for lab in labs:
    #     eids, dets = one.search(
    #         task_protocol="ephysChoiceWorld6.2.5",
    #         lab=lab,
    #         details=True,
    #         dataset_types=["_iblrig_taskData.raw", "_iblrig_taskSettings.raw"],
    #     )
    #     print(lab, len(eids))
    # for eid in eids:
    #     plot_session_trigger_response_diffs(eid)
    lab = "churchlandlab"
    eid = "0deb75fb-9088-42d9-b744-012fb8fc4afb"

    bla1, bla2 = get_bpod_fronts(eid)
    # for lab in labs:
    #     describe_lab_trigger_response_diffs(lab)
    eid = "2e6e179c-fccc-4e8f-9448-ce5b6858a183"
