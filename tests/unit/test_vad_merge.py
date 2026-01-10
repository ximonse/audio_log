from daylog.pipeline.vad import merge_segments


def test_merge_segments_gap():
    segments = [(0.0, 1.0), (1.4, 2.0), (3.0, 3.5)]
    merged = merge_segments(segments, merge_gap_s=0.5)
    assert merged == [(0.0, 2.0), (3.0, 3.5)]


def test_merge_segments_no_merge():
    segments = [(0.0, 1.0), (1.7, 2.0)]
    merged = merge_segments(segments, merge_gap_s=0.5)
    assert merged == [(0.0, 1.0), (1.7, 2.0)]