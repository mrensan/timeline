#!/usr/bin/env python3
import sys
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

DEFAULT_MIN_BREAK_SECONDS = 300  # 5 minutes — overridable via timewarrior.cfg

def parse_iso(ts_str):
    """Parse Timewarrior ISO 8601 timestamp string into UTC datetime."""
    # Format: YYYYMMDDTHHMMSSZ or Standard ISO
    ts_clean = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_clean)
    except ValueError:
        return datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

def format_duration(seconds):
    """Format total seconds as H:MM:SS."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"

def underline(text: str) -> str:
    return f"\033[4m{text}\033[0m"

def overline(text: str) -> str:
    return f"\033[53m{text}\033[0m"

def merge_intervals(intervals, min_break=DEFAULT_MIN_BREAK_SECONDS):
    """Merge chronologically sorted intervals for one day.

    Short gaps (< min_break seconds) are ignored: the two surrounding blocks
    are merged and only actual work time is counted.  Long gaps produce separate
    blocks.  Returns a list of (display_start, display_end, actual_seconds).
    """
    curr_start, curr_end = intervals[0]
    curr_seconds = (curr_end - curr_start).total_seconds()
    merged = []

    for next_start, next_end in intervals[1:]:
        gap = (next_start - curr_end).total_seconds()
        seg_seconds = (next_end - next_start).total_seconds()
        if gap < min_break:
            curr_end = next_end
            curr_seconds += seg_seconds
        else:
            merged.append((curr_start, curr_end, curr_seconds))
            curr_start, curr_end = next_start, next_end
            curr_seconds = seg_seconds

    merged.append((curr_start, curr_end, curr_seconds))
    return merged


def parse_headers(stream):
    """Read Timewarrior config header lines and return them as a dict."""
    config = {}
    for line in stream:
        if line == '\n' or not line:
            break
        if ': ' in line:
            key, _, value = line.partition(': ')
            config[key.strip()] = value.strip()
    return config


def main():
    config = parse_headers(sys.stdin)

    try:
        min_break = int(config.get('timeline.min_break', DEFAULT_MIN_BREAK_SECONDS))
    except ValueError:
        min_break = DEFAULT_MIN_BREAK_SECONDS

    # Read JSON payload from Timewarrior
    data = sys.stdin.read().strip()
    if not data:
        print("No data recorded for this range.")
        return

    intervals = json.loads(data)
    if not intervals:
        print("No data recorded for this range.")
        return

    now = datetime.now(timezone.utc)
    parsed_intervals = []

    for i in intervals:
        start = parse_iso(i["start"])
        end = parse_iso(i["end"]) if "end" in i else now
        if end > start:
            parsed_intervals.append((start, end))

    # Sort intervals chronologically
    parsed_intervals.sort(key=lambda x: x[0])

    # Group intervals by local calendar day (or UTC date based on timestamps)
    days = defaultdict(list)
    for start, end in parsed_intervals:
        day_key = start.astimezone().strftime("%Y-%m-%d")
        days[day_key].append((start.astimezone(), end.astimezone()))

    grand_total_seconds = 0

    header = f"{underline('Wk ')} {underline('Date      ')} {underline('Day      ')} {underline('    Start')} {underline('      End')} {underline('    Time')} {underline('    Total')}"
    print(header)
    for day_str in sorted(days.keys()):
        day_intervals = days[day_str]
        merged_blocks = merge_intervals(day_intervals, min_break)

        # Calculate daily total duration (sum of actual work seconds, gaps excluded)
        day_seconds = sum(secs for _, _, secs in merged_blocks)
        grand_total_seconds += day_seconds

        # Format day header (e.g. W39 2026-09-24 Thu)
        first_date = merged_blocks[0][0]
        week_num = first_date.strftime("W%V")
        date_formatted = first_date.strftime("%Y-%m-%d %a")
        day_header = f"{week_num} {date_formatted}"

        # Print daily output
        for idx, (block_start, block_end, block_seconds) in enumerate(merged_blocks):
            b_start_str = block_start.strftime("%H:%M:%S")
            b_end_str = block_end.strftime("%H:%M:%S")
            b_dur_str = format_duration(block_seconds)

            if idx == 0:
                # First block line includes header and daily total
                print(f"{day_header:<25} {b_start_str:>8}  {b_end_str:>8} {b_dur_str:>8}")
            else:
                # Subsequent block lines (after a break)
                print(f"{'':<25} {b_start_str:>8}  {b_end_str:>8} {b_dur_str:>8}")

        # Print daily summary total at the end of the day's blocks
        day_tot_str = format_duration(day_seconds)
        print(f"{'':<54} {day_tot_str:>8}\n")

    # Print grand accumulated total for all requested days
    grand_tot_str = format_duration(grand_total_seconds)
    start_col = 62-len(grand_tot_str)
    print(f"{'':<{start_col}} {overline(grand_tot_str):>8}")

if __name__ == '__main__':
    main()
