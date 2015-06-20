# -*- coding: utf-8 -*-

"""Tests of clustering algorithms."""

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import os.path as op

import numpy as np

from ...utils.tempdir import TemporaryDirectory
from ...utils.settings import Settings
from ..algorithms import cluster, SpikeDetekt
from ...io.kwik import KwikModel
from ...io.kwik.mock import create_mock_kwik
from ...io.mock import artificial_traces


#------------------------------------------------------------------------------
# Tests
#------------------------------------------------------------------------------

def test_spike_detect():
    sample_rate = 10000
    n_samples = 10000
    n_channels = 4
    traces = artificial_traces(n_samples, n_channels)

    # Load default settings.
    curdir = op.dirname(op.realpath(__file__))
    default_settings_path = op.join(curdir, '../default_settings.py')
    settings = Settings(default_path=default_settings_path)
    params = settings['spikedetekt_params'](sample_rate)
    params['sample_rate'] = sample_rate
    params['probe_adjacency_list'] = {0: [1, 2], 1: [0, 2], 2: [0, 1], 3: []}
    params['probe_channels'] = {0: list(range(n_channels))}

    sd = SpikeDetekt(**params)

    # Filter the data.
    traces_f = sd.apply_filter(traces)
    assert traces_f.shape == traces.shape
    assert not np.any(np.isnan(traces_f))

    # Thresholds.
    thresholds = sd.find_thresholds(traces)
    assert 0 < thresholds['weak'] < thresholds['strong']

    # Spike detection.
    traces_f[1000:1010, :3] *= 5
    traces_f[2000:2010, [0, 2]] *= 5
    traces_f[3000:3020, :] *= 5
    components = sd.detect(traces_f, thresholds)
    assert isinstance(components, list)
    n_spikes = len(components)
    n_samples_waveforms = (params['extract_s_before'] +
                           params['extract_s_after'])

    # Spike extraction.
    samples, waveforms, masks = sd.extract_spikes(components,
                                                  traces_f,
                                                  thresholds=thresholds,
                                                  )
    assert samples.dtype == np.uint64
    assert samples.shape == (n_spikes,)
    assert waveforms.shape == (n_spikes, n_samples_waveforms, n_channels)
    assert masks.shape == (n_spikes, n_channels)
    assert 0. <= masks.min() < masks.max() <= 1.
    assert not np.any(np.isnan(samples))
    assert not np.any(np.isnan(waveforms))
    assert not np.any(np.isnan(masks))

    # PCA.
    pcs = sd.waveform_pcs(waveforms, masks)
    n_pcs = params['nfeatures_per_channel']
    assert pcs.shape == (n_pcs, n_samples_waveforms, n_channels)
    assert not np.any(np.isnan(pcs))

    # Features.
    features = sd.features(waveforms, pcs)
    assert features.shape == (n_spikes, n_channels, n_pcs)
    assert not np.any(np.isnan(features))


def test_cluster():
    n_spikes = 100
    with TemporaryDirectory() as tempdir:
        filename = create_mock_kwik(tempdir,
                                    n_clusters=1,
                                    n_spikes=n_spikes,
                                    n_channels=8,
                                    n_features_per_channel=3,
                                    n_samples_traces=5000)
        model = KwikModel(filename)

        spike_clusters = cluster(model, num_starting_clusters=10)
        assert len(spike_clusters) == n_spikes

        spike_clusters = cluster(model, num_starting_clusters=10,
                                 spike_ids=range(100))
        assert len(spike_clusters) == 100
