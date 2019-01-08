# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, October 11th 2018, 12:11:13 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 11-10-2018 12:11:26.2626
"""
Find task name
Check if extractors for specific task exist
Extract data OR return error to user saying that the task has no extractors
"""
import logging
from pathlib import Path

from alf.extractors import training_trials, training_wheel
from ibllib.io import raw_data_loaders as raw

logger_ = logging.getLogger('ibllib.alf')


def extractors_exist(session_path):
    settings = raw.load_settings(session_path)
    task_name = settings['PYBPOD_PROTOCOL']
    task_name = task_name.split('_')[-1]
    extractor_type = task_name[:task_name.find('ChoiceWorld')]
    if any([extractor_type in x for x in globals()]):
        return extractor_type
    else:
        logger_.warning(f"No extractors were found for {extractor_type}ChoiceWorld")
        return False


def is_extracted(session_path):
    sp = Path(session_path)
    if (sp / 'alf').exists():
        return True
    else:
        return False


def from_path(session_path, force=False, save=True):
    """
    Extract a session from full ALF path (ex: '/scratch/witten/ibl_witten_01/2018-12-18/001')
    force: (False) overwrite existing files
    save: (True) boolean or list of ALF file names to extract
    """
    extractor_type = extractors_exist(session_path)
    if is_extracted(session_path) and not force:
        print(f"Session {session_path} already extracted.")
        return

    if extractor_type == 'training':
        training_trials.extract_all(session_path, save=save)
        training_wheel.extract_all(session_path, save=save)


def bulk(subjects_folder):
    ses_path = Path(subjects_folder).glob('**/extract_me.flag')
    for p in ses_path:
        logger_.info('Extracting ' + str(p.parent))
        # the flag file may contains specific file names for a targeted extraction
        save = raw.read_flag_file(p)
        try:
            from_path(p.parent, force=True, save=save)
        except (ValueError, FileNotFoundError) as e:
            error_message = str(p.parent) + ' failed extraction' + '\n    ' + str(e)
            logging.error(error_message)
            err_file = p.parent.joinpath('extract_me.error')
            p.rename(err_file)
            with open(err_file, 'w+') as f:
                f.write(error_message)
            continue
        p.rename(p.parent.joinpath('register_me.flag'))


def create_extract_flags(root_data_folder):
    # first part is to create extraction flags
    ses_path = Path(root_data_folder).glob('**/raw_behavior_data')
    for p in ses_path:
        flag_file = Path(p).parent.joinpath('extract_me.flag')
        if p.parent.joinpath('flatiron.flag').is_file():
            continue
        if p.parent.joinpath('extract_me.error').is_file():
            continue
        if p.parent.joinpath('register_me.error').is_file():
            continue
        with open(flag_file, 'w+') as f:
            f.write('')
        print(flag_file)
