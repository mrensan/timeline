# timeline — Timewarrior extension

[![Tests](https://github.com/mrensan/timeline/actions/workflows/test.yml/badge.svg)](https://github.com/mrensan/timeline/actions/workflows/test.yml)

A [Timewarrior](https://timewarrior.net/) extension that shows a high-level timeline of your working day, week, or any date range — without caring about individual task tags.

## What is Timewarrior?

Timewarrior is a free, open-source command-line time tracker. You start and stop tracking with `timew start` / `timew stop`, optionally tagging each interval (e.g. `timew start project-x meeting`). It stores every tracked interval with its start time, end time, and tags.

The built-in `summary` command reports each interval individually, grouped by tag. That's great for billing by project, but it produces a lot of noise when you just want to know *when* you worked and how long each session was.

## What `timeline` does differently

`timeline` ignores tags entirely and focuses on **working sessions** — contiguous blocks of time where you were active, separated by meaningful breaks.

- Short gaps between intervals (under 5 minutes by default) are treated as momentary interruptions and **merged** into the surrounding session. The gap itself is not counted toward working time.
- Longer gaps are treated as real breaks and produce a new session line.
- The break threshold is configurable (see [Configuration](#configuration) below).

This makes it suitable for workplaces that need to record working hours and break times regardless of what tasks were actually being worked on.

## Synopsis

```
timew timeline [<range>] [<tag>…]
```

Same syntax as `timew summary`. Examples:

```
timew timeline
timew timeline today
timew timeline 2026-09-17 - 2026-09-19
timew timeline :week
```

## Example output

### `timew summary 2026-09-17 - 2026-09-19`

```
Wk  Date       Day ID  Tags    Annotation    Start      End    Time    Total
W38 2026-09-17 Thu @48 d-2120              9:00:00 10:52:59 1:52:59
                   @47 d-2120             10:52:59 12:50:40 1:57:41
                   @46 SEC, TW            13:39:37 16:01:39 2:22:02
                   @45 d-2120             17:04:13 17:54:56 0:50:43
                   @44                    20:56:22 23:09:32 2:13:10  9:16:35
W38 2026-09-18 Fri @43 d-2120             10:49:22 14:51:27 4:02:05
                   @42 d-2120             14:53:00 16:41:00 1:48:00
                   @41                    18:05:00 19:31:25 1:26:25
                   @40 d-2120             21:14:36 21:16:43 0:02:07
                   @39 TW                 21:16:43 21:19:05 0:02:22
                   @38 SEC, TW            21:19:05 21:26:42 0:07:37
                   @37 SEC     work on tw 21:27:00 22:34:58 1:07:58  8:36:34

                                                                    17:53:09
```

### `timew timeline 2026-09-17 - 2026-09-19`

```
Wk  Date       Day           Start       End     Time     Total
W38 2026-09-17 Thu        09:00:00  12:50:40  3:50:40
                          13:39:37  16:01:39  2:22:02
                          17:04:13  17:54:56  0:50:43
                          20:56:22  23:09:32  2:13:10
                                                        9:16:35

W38 2026-09-18 Fri        10:49:22  16:41:00  5:50:05
                          18:05:00  19:31:25  1:26:25
                          21:14:36  22:34:58  1:20:04
                                                        8:36:34

                                                       17:53:09
```

Notice that on 2026-09-17, the first two intervals (`@48` and `@47`) share no gap so they appear as a single session `09:00:00 – 12:50:40`. On 2026-09-18, the four late-evening intervals (`@40`–`@37`) have gaps of only 1–2 minutes between them and are collapsed into one session `21:14:36 – 22:34:58`, with only the actual tracked time counted (not the gaps).

## Installation

**Please note** you need **Python 3.10** or later to run this extension.

### 1. Find your extensions directory

The path depends on your OS and how Timewarrior was installed. The safest way is to ask Timewarrior itself:

```
timew diagnostics
```

Look for the `extensions` line in the output — it shows the exact path in use on your system.

Common locations:

| Platform | Typical path |
|---|---|
| macOS (Homebrew) | `~/.config/timewarrior/extensions/` |
| Linux (XDG) | `~/.config/timewarrior/extensions/` |
| Linux (older / manual build) | `~/.timewarrior/extensions/` |

### 2. Install the extension

Replace `EXTENSIONS_DIR` with the path from step 1:

```
ln -s /path/to/timeline.py EXTENSIONS_DIR/timeline
chmod +x EXTENSIONS_DIR/timeline
```

### 3. Verify Timewarrior sees it

```
timew extensions
```

### 4. Run it

```
timew timeline
```

## Configuration

`timeline` reads your `timewarrior.cfg` for a single optional setting:

| Key | Type | Default | Description |
|---|---|---|---|
| `timeline.min_break` | integer (seconds) | `300` | Gaps shorter than this are merged; longer gaps are treated as real breaks. |

Add the line to your `timewarrior.cfg` to override the default. For example, to use a 10-minute threshold:

```
timeline.min_break=600
```

The config file location depends on your OS and installation method. Run `timew diagnostics` to find it.

## How it works (for extension authors)

Timewarrior passes all data to the extension via **stdin** in two parts, separated by a blank line:

1. **Configuration headers** — `name: value` pairs (the full contents of `timewarrior.cfg` plus temporary report metadata)
2. **JSON array** — one object per tracked interval: `{"start":"20160405T162205Z","end":"20160405T162211Z","tags":["tag1","tag2"]}`

`timeline.py` reads the config headers to pick up `timeline.min_break` (falling back to 300 s), discards tags, sorts intervals by day, merges those separated by less than the threshold (counting only actual work time, not the gap), and prints the formatted output.

## Running the tests

```
python -m pytest test_timeline.py -v
```
