
"""
GLM fitting utilities based on NeuroGLM by Il Memming Park, Jonathan Pillow:

https://github.com/pillowlab/neuroGLM

Berk Gercek
International Brain Lab, 2020
"""
from warnings import warn
import numpy as np
import pandas as pd
# from brainbox.processing import bincount2D
import scipy.sparse as sp
import numba as nb


class NeuralGLM:
    """
    Generalized Linear Model which seeks to describe spiking activity as the output of a poisson
    process. Uses sklearn's GLM methods under the hood while providing useful routines for dealing
    with neural data
    """

    def __init__(self, trialsdf, spk_times, spk_clu, vartypes,
                 binwidth=0.02, mintrials=100):
        """
        Construct GLM object using information about all trials, and the relevant spike times.
        Only ingests data, and further object methods must be called to describe kernels, gain
        terms, etc. as components of the model.

        Parameters
        ----------
        trialsdf: pandas.DataFrame
            DataFrame of trials in which each row contains all desired covariates of the model.
            e.g. contrast, stimulus type, etc. Not all columns will necessarily be fit.
            If a continuous covariate (e.g. wheel position, pupil diameter) is included, each entry
            of the column must be a nSamples x 2 array with samples in the first column and
            timestamps (relative to trial start) in the second position.
            *Must have \'trial_start\' and \'trial_end\' parameters which are times, in seconds.*
        spk_times: numpy.array of floats
            1-D array of times at which spiking events were detected, in seconds.
        spk_clu: numpy.array of integers
            1-D array of same shape as spk_times, with integer cluster IDs identifying which
            cluster a spike time belonged to.
        vartypes: dict
            Dict with column names in trialsdf as keys, values are the type of covariate the column
            contains. e.g. {'stimOn_times': 'timing', 'wheel', 'continuous', 'correct': 'value'}
            Valid values are:
                'timing' : A timestamp relative to trial start (e.g. stimulus onset)
                'continuous' : A continuous covariate sampled throughout the trial (e.g. eye pos)
                'value' : A single value for the given trial (e.g. contrast or difficulty)
        binwidth: float
            Width, in seconds, of the bins which will be used to count spikes. Defaults to 20ms.
        bintrials: int
            Minimum number of trials in which neurons fired a spike in order to be fit. Defaults
            to 100 trials.

        Returns
        -------
        glm: object
            GLM object with methods for adding regressors and fitting
        """
        # Data checks #
        if not all([name in vartypes for name in trialsdf.columns]):
            raise KeyError("Some columns were not described in vartypes")
        if not all([value in ('timing', 'continuous', 'value') for value in vartypes.values()]):
            raise ValueError("Invalid values were passed in vartypes")
        if not len(spk_times) == len(spk_clu):
            raise IndexError("Spike times and cluster IDs are not same length")

        # Filter out cells which don't meet the criteria for minimum spiking, while doing trial
        # assignment
        self.binf = lambda t: np.ciel(t / binwidth).astype(int)  # Useful step counter fn
        clu_ids = np.unique(spk_clu)
        trialspiking = np.zeros((spk_clu.max() + 1, len(trialsdf.index)))
        trbounds = trialsdf[['trial_start', 'trial_end']].values
        st_endlast = 0
        trialspiking = np.zeros((len(trialsdf.index), len(clu_ids) + 1), dtype=bool)
        trialsdf['spikes'] = np.nan
        trialsdf['clu'] = np.nan
        trialsdf['duration'] = np.nan
        for i, (start, end) in enumerate(trbounds):
            if any(np.isnan((start, end))):
                warn(f"NaN values found in trial start or end at trial number {i}. "
                     "Discarding trial.")
                trialsdf.drop(i, inplace=True)
                continue
            st_startind = np.searchsorted(spk_times[st_endlast:], start) + st_endlast
            st_endind = np.searchsorted(spk_times[st_endlast:], end, side='right') + st_endlast
            st_endlast = st_endind
            trial_clu = np.unique(spk_clu[st_startind:st_endind])
            trialspiking[i, trial_clu] = True
            trialsdf.loc[i, 'spikes'] = spk_times[st_startind:st_endind] - start
            trialsdf.loc[i, 'clu'] = spk_clu[st_startind:st_endind]
            trialsdf.loc[i, 'duration'] = end - start
        self.clu_ids = np.argwhere(np.sum(trialspiking, axis=0) > mintrials)
        self.covar = {}
        return

    def add_covariate_timing(self, covlabel, eventname, bases,
                             offset=0, deltaval=None, cond=None, desc=''):
        """
        Convenience wrapper for adding timing event regressors to the GLM. Automatically generates
        a one-hot vector for each trial as the regressor and adds the appropriate data structure
        to the model.

        Parameters
        ----------
        covlabel : str
            Label which the covariate will use. Can be accessed via dot syntax of the instance
            usually.
        eventname : str
            Label of the column in trialsdf which has the event timing for each trial.
        bases : numpy.array
            nTB x nB array, i.e. number of time bins for the bases functions by number of bases.
            Each column in the array is used together to describe the response of a unit to that
            timing event.
        offset : float, seconds
            Offset of bases functions relative to timing event. Negative values will ensure that

        deltaval : None, str, or pandas series, optional
            Values of the kronecker delta function peak used to encode the event. If a string, the
            column in trialsdf with that label will be used. If a pandas series with indexes
            matching trialsdf, corresponding elements of the series will be the delta funtion val.
            If None (default) height is 1.
        cond : None, list, or fun, optional
            Condition which to apply this covariate. Can either be a list of trial indices, or a
            function which takes in rows of the trialsdf and returns booleans.
        desc : str, optional
            Additional information about the covariate, if desired. by default ''
        """
        if deltaval is None:
            gainmod = False
        elif isinstance(deltaval, pd.Series):
            gainmod = True
        else:
            raise TypeError(f'deltaval must be None or pandas series. {type(deltaval)} '
                            'was passed instead.')
        if eventname not in self.vartypes:
            raise ValueError('Event name specified not found in trialsdf')
        elif self.vartypes[eventname] != 'timing':
            raise TypeError(f'Column {eventname} in trialsdf is not registered as a timing')

        vecsizes = self.trialsdf['duration'].apply(self.binf)
        stiminds = self.trialsdf[eventname].apply(self.binf)
        stimvecs = []
        for i in self.trialsdf.index:
            vec = np.zeros(vecsizes[i])
            if gainmod:
                vec[stiminds[i]] = deltaval[i]
            else:
                vec[stiminds[i]] = 1
            stimvecs.append(vec)
        regressor = pd.Series(stimvecs, index=self.trialsdf.index)
        self.add_covariate(covlabel, regressor, bases, offset, cond, desc)
        return

    def add_covariate_boxcar(self, covlabel, boxstart, boxend,
                             cond=None, height=None, desc=''):
        if isinstance(height, str):
            if height in self.trialsdf.columns:
                height = self.trialsdf[height]
            else:
                raise KeyError(f'{height} is str not in columns of trialsdf')
        elif isinstance(height, pd.Series):
            if not all(height.index == self.trialsdf.index):
                raise IndexError('Indices of height series does not match trialsdf.')
        elif height is None:
            height = pd.Series(np.ones(len(self.trialsdf.index)), index=self.trialsdf.index)
        vecsizes = self.trialsdf['duration'].apply(self.binf)
        stind = self.trialsdf[boxstart].apply(self.binf)
        endind = self.trialsdf[boxend].apply(self.binf)
        stimvecs = []
        for i in self.trialsdf.index:
            bxcar = np.zeros(vecsizes[i])
            bxcar[stind:endind + 1] = height[i]
            stimvecs.append(bxcar)
        regressor = pd.Series(stimvecs, index=self.trialsdf.index)
        self.add_covariate(covlabel, regressor, None, cond, desc)
        return

    def add_covariate_raw(self, covlabel, rawcolname,
                          desc=''):
        raise NotImplementedError('No support for raw covariates at this time. Coming soon™')

    def add_covariate(self, covlabel, regressor, bases,
                      offset=0, cond=None, desc=''):
        """
        Parent function to add covariates to model object. Takes a regressor in the form of a
        pandas Series object, a T x M array of M bases, and stores them for use in the design
        matrix generation.

        Parameters
        ----------
        covlabel : str
            Label for the covariate being added. Will be exposed, if possible, through
            (instance).(covlabel) attribute.
        regressor : pandas.Series
            Series in which each element is the value(s) of a regressor for a trial at that index.
            These will be convolved with the bases functions (if provided) to produce the
            components of the design matrix. *Regressor must be (T / dt) x 1 array for each trial*
        bases : numpy.array or None
            T x M array of M basis functions over T timesteps. Columns will be convolved with the
            elements of `regressor` to produce elements of the design matrix. If None, it is
            assumed a raw regressor is being used.
        offset : int, optional
            Offset of the regressor from the bases during convolution. Negative values indicate
            that the firing of the unit will be , by default 0
        cond : list or func, optional
            Condition for which to apply covariate. Either a list of trials which the covariate
            applies to, or a function of the form f(dataframerow) which returns a boolean,
            by default None
        desc : str, optional
            Description of the covariate for reference purposes, by default '' (empty)
        """
        # Test for mismatch in length of regressor vs trials
        mismatch = np.zeros(len(self.trialsdf.index), dtype=bool)
        for i in self.trialsdf.index:
            currtr = self.trialsdf.loc[i]
            nT = self.binf(currtr.duration)
            if regressor.loc[i].shape[0] != nT:
                mismatch[i] = True

        if np.any(mismatch):
            raise ValueError('Length mismatch between regressor and trial on trials'
                             f'{*np.argwhere(mismatch)}.')

        # Initialize containers for the covariate dicts
        if not hasattr(self, 'currcol'):
            self.currcol = 0
        if callable(cond):
            cond = self.trialsdf.index[self.trialsdf.apply(cond, axis=1)].to_numpy()
        if not all(regressor.index == self.trialsdf.index):
            raise IndexError('Indices of regressor and trials dataframes do not match.')

        cov = {'description': desc,
               'bases': bases,
               'valid_trials': cond,
               'offset': offset,
               'regressor': regressor,
               'dmcol_idx': np.arange(self.currcol, self.currcol + bases.shape[1])
               if bases is not None else self.currcol}
        if bases is None:
            self.currcol += 1
        else:
            self.currcol += bases.shape[1]

        self.covar[covlabel] = cov
        return

    def compile_design_matrix(self):
        covars = self.covar
        # Go trial by trial and compose smaller design matrices
        sparseDMs = []
        for i, trial in self.trialsdf.iterrows():
            nT = self.binf(trial.trial_end - trial.trial_start)
            miniX = np.zeros((nT, self.edim))
            for cov in covars:
                sidx = cov['dmcol_idx']
                # Optionally use cond to filter out which trials to apply certain regressors,
                if i not in cov['valid_trials']:
                    continue
                stim = cov['regressor']
                # Convolve Kernel or basis function with stimulus or regressor
                if cov['bases'] is None:
                    miniX[:, sidx] = stim
                else:
                    miniX[:, sidx] = denseconv(stim, cov['bases'])
            # Sparsify convolved result and store in sparseDMs
            sparseDMs.append(sp.lil_matrix(miniX))
        sparseX = sp.vstack(sparseDMs)
        self.dm = sparseX
        return


def convbasis(stim, bases, offset=0):
    if offset < 0:
        stim = np.pad(stim, ((0, offset), (0, 0)))
    elif offset > 0:
        stim = np.pad(stim, ((offset, 0), (0, 0)))

    X = denseconv(stim, bases, np.ones((stim.shape[1], bases.shape[1]), dtype=bool))

    if offset < 0:
        X = X[-offset:, :]
    elif offset > 0:
        X = X[: -(1 + offset), :]
    return X

# Precompilation for speed
@nb.njit
def denseconv(X, bases):
    T, dx = X.shape
    TB, M = bases.shape
    indices = np.ones((dx, M))
    sI = np.sum(indices, axis=1)
    BX = np.zeros((T, np.sum(sI)))
    sI = np.cumsum(sI)
    k = 0
    for kCov in range(dx):
        A = np.zeros((T + TB - 1, np.sum(indices[kCov, :])))
        for i, j in enumerate(np.argwhere(indices[kCov, :]).flat):
            A[:, i] = np.convolve(X[:, kCov], bases[:, j])
        BX[:, k: sI[kCov]] = A[: T, :]
        k = sI[kCov]
    return BX