import io
import pytest
from datetime import datetime, timezone, timedelta
from timeline import merge_intervals, parse_headers, DEFAULT_MIN_BREAK_SECONDS as MIN_BREAK_SECONDS

def dt(h, m, s=0):
    """UTC datetime on an arbitrary fixed date for testing."""
    return datetime(2026, 1, 1, h, m, s, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# merge_intervals
# ---------------------------------------------------------------------------

class TestMergeIntervals:

    def test_single_interval(self):
        intervals = [(dt(9, 0), dt(10, 0))]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 1
        start, end, secs = blocks[0]
        assert start == dt(9, 0)
        assert end == dt(10, 0)
        assert secs == 3600

    def test_short_gap_merges_and_excludes_gap(self):
        # 30-min work, 1-min gap (< 5 min threshold), 30-min work
        # Expected: one block spanning 09:00–10:31, but only 3600 s counted
        gap_seconds = 60
        intervals = [
            (dt(9, 0), dt(9, 30)),
            (dt(9, 31), dt(10, 1)),
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 1
        start, end, secs = blocks[0]
        assert start == dt(9, 0)
        assert end == dt(10, 1)
        assert secs == 30 * 60 + 30 * 60  # 3600, gap NOT included

    def test_long_gap_produces_two_blocks(self):
        # 30-min work, 10-min gap (> 5 min threshold), 30-min work
        intervals = [
            (dt(9, 0), dt(9, 30)),
            (dt(9, 40), dt(10, 10)),
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 2
        _, _, secs0 = blocks[0]
        _, _, secs1 = blocks[1]
        assert secs0 == 30 * 60
        assert secs1 == 30 * 60

    def test_gap_exactly_at_threshold_splits(self):
        # A gap of exactly MIN_BREAK_SECONDS should NOT merge (gap < threshold)
        intervals = [
            (dt(9, 0), dt(9, 30)),
            (dt(9, 30) + timedelta(seconds=MIN_BREAK_SECONDS), dt(10, 0)),
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 2

    def test_gap_one_second_below_threshold_merges(self):
        intervals = [
            (dt(9, 0), dt(9, 30)),
            (dt(9, 30) + timedelta(seconds=MIN_BREAK_SECONDS - 1), dt(10, 0)),
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 1

    def test_multiple_short_gaps_all_merged(self):
        # Three 20-min segments with 2-min gaps between them
        intervals = [
            (dt(9, 0),  dt(9, 20)),
            (dt(9, 22), dt(9, 42)),
            (dt(9, 44), dt(10, 4)),
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 1
        start, end, secs = blocks[0]
        assert start == dt(9, 0)
        assert end == dt(10, 4)
        assert secs == 3 * 20 * 60  # 3600 s, two 2-min gaps excluded

    def test_mixed_gaps(self):
        # short gap → merge, long gap → split
        intervals = [
            (dt(9, 0),  dt(9, 30)),   # seg 1
            (dt(9, 31), dt(10, 0)),   # seg 2 — 1-min gap, merges with seg 1
            (dt(10, 20), dt(11, 0)),  # seg 3 — 20-min gap, new block
        ]
        blocks = merge_intervals(intervals)
        assert len(blocks) == 2

        start0, end0, secs0 = blocks[0]
        assert start0 == dt(9, 0)
        assert end0 == dt(10, 0)
        assert secs0 == 30 * 60 + 29 * 60  # 59 min, 1-min gap excluded

        start1, end1, secs1 = blocks[1]
        assert start1 == dt(10, 20)
        assert end1 == dt(11, 0)
        assert secs1 == 40 * 60

    def test_custom_threshold_respected(self):
        # With a 10-minute threshold, a 7-minute gap should merge
        intervals = [
            (dt(9, 0),  dt(9, 30)),
            (dt(9, 37), dt(10, 0)),
        ]
        blocks = merge_intervals(intervals, min_break=600)
        assert len(blocks) == 1
        _, _, secs = blocks[0]
        assert secs == 30 * 60 + 23 * 60  # gap excluded

    def test_custom_threshold_splits_when_gap_exceeds_it(self):
        # With a 3-minute threshold, a 4-minute gap should split
        intervals = [
            (dt(9, 0),  dt(9, 30)),
            (dt(9, 34), dt(10, 0)),
        ]
        blocks = merge_intervals(intervals, min_break=180)
        assert len(blocks) == 2

    def test_display_start_end_span_whole_session(self):
        # Even after merging, display_start/end bracket the full session
        intervals = [
            (dt(9, 0),  dt(9, 30)),
            (dt(9, 33), dt(10, 0)),
        ]
        blocks = merge_intervals(intervals)
        start, end, _ = blocks[0]
        assert start == dt(9, 0)
        assert end == dt(10, 0)


# ---------------------------------------------------------------------------
# parse_headers
# ---------------------------------------------------------------------------

class TestParseHeaders:

    def _stream(self, text):
        return io.StringIO(text)

    def test_reads_key_value_pairs(self):
        stream = self._stream("color: on\nreport: day\n\n")
        config = parse_headers(stream)
        assert config["color"] == "on"
        assert config["report"] == "day"

    def test_stops_at_blank_line(self):
        stream = self._stream("color: on\n\ntimeline.min_break: 600\n")
        config = parse_headers(stream)
        assert "color" in config
        assert "timeline.min_break" not in config  # after blank line, not read

    def test_timeline_min_break_present(self):
        stream = self._stream("color: on\ntimeline.min_break: 600\n\n")
        config = parse_headers(stream)
        assert config["timeline.min_break"] == "600"

    def test_empty_headers(self):
        stream = self._stream("\n")
        config = parse_headers(stream)
        assert config == {}

    def test_value_with_colon(self):
        # Values that themselves contain ': ' should not be split further
        stream = self._stream("temp.db: /home/user/.config/timew: extra\n\n")
        config = parse_headers(stream)
        assert config["temp.db"] == "/home/user/.config/timew: extra"

    def test_default_used_when_key_absent(self):
        config = {}
        min_break = int(config.get("timeline.min_break", MIN_BREAK_SECONDS))
        assert min_break == MIN_BREAK_SECONDS

    def test_config_value_overrides_default(self):
        config = {"timeline.min_break": "900"}
        min_break = int(config.get("timeline.min_break", MIN_BREAK_SECONDS))
        assert min_break == 900
