#!/usr/bin/env python3
"""ASV -- Mains interference / electrode contact checker
======================================================
Captures a few seconds of live signal and reports whether the front end is
measuring muscle or 50 Hz mains hum.

Built after the 2026-08-23 fault: peak-to-peak jumped from ~100 mV to ~3000 mV
and three electrode swaps changed nothing, because the electrodes were never the
problem -- 78% of the signal power was sitting at 50 Hz. Once the AD8232 is
driven rail-to-rail by mains common-mode, no software notch can recover the
muscle signal, so this has to be caught BEFORE recording a dataset.

Use it to A/B a fix in seconds (charger unplugged vs plugged, reference
electrode reseated, moved away from a power strip):

    python tools/check_interference.py --port COM5
    python tools/check_interference.py --port COM5 --seconds 5
"""
import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml.acquisition.serial_reader import EMGSerialReader
from ml.refined.utterance_features import FS_DEFAULT, UV_PER_LSB, signal_health

# Healthy reference values measured on the good 2026-08-26 S01 batch.
GOOD_PP_MV = (50.0, 600.0)      # observed 56 .. 498 mV across 50 recordings
MAINS_FRACTION_WARN = 0.15      # good batch sat at 3.7% of power near 50 Hz
MAINS_FRACTION_BAD = 0.35


def band_fraction(x, fs, lo, hi):
    f = np.fft.rfftfreq(len(x), 1.0 / fs)
    p = np.abs(np.fft.rfft(x)) ** 2
    total = p[1:].sum()
    if total <= 0:
        return 0.0
    return float(p[(f >= lo) & (f < hi)].sum() / total)


def analyse(counts, fs, mains_hz):
    counts = np.asarray(counts, dtype=float)
    health = signal_health(counts)
    x = (counts - counts.mean()) * UV_PER_LSB / 1000.0

    # Rail proximity: single-ended full scale at gain idx 1 is ~26500 counts.
    lo_rail = float(counts.min()) < 2000
    hi_rail = float(counts.max()) > 24500

    return {
        "health": health,
        "mains": band_fraction(x, fs, mains_hz - 5, mains_hz + 5),
        "harmonic": band_fraction(x, fs, 2 * mains_hz - 5, 2 * mains_hz + 5),
        "emg": band_fraction(x, fs, 20, 200),
        "drift": band_fraction(x, fs, 0.1, 5),
        "min_counts": float(counts.min()),
        "max_counts": float(counts.max()),
        "railing": lo_rail or hi_rail,
    }


def verdict(r):
    """Returns (headline, list of next actions)."""
    h = r["health"]
    if h["status"] == "NO_DATA":
        return "NO DATA", ["No samples arrived. Check the port and that nothing else holds it."]
    if h["status"] == "FLAT":
        return "FLAT - no contact", [
            "Signal is nearly a straight line: an electrode lead is open.",
            "Check the 3.5 mm jack is fully clicked in and each snap is seated.",
        ]

    if r["mains"] >= MAINS_FRACTION_BAD or (r["railing"] and r["mains"] >= MAINS_FRACTION_WARN):
        return "MAINS INTERFERENCE - do not record", [
            "Unplug the laptop charger and run on battery. This alone fixes it most of the time.",
            "Reseat the REFERENCE (RL) electrode -- it is the one that cancels common mode.",
            "  Put it on bone, not muscle: mastoid behind the ear, or the collarbone.",
            "Move away from power strips, chargers and fluorescent lights.",
            "Confirm AD8232 GND and ESP32 GND really are connected.",
            "Twist the electrode leads together and keep them short.",
        ]
    if r["mains"] >= MAINS_FRACTION_WARN:
        return "ELEVATED MAINS HUM - usable but worth fixing", [
            "Try unplugging the laptop charger and re-running this check.",
            "Reseat the reference electrode.",
        ]
    if r["railing"]:
        return "SATURATING - front end hitting the rails", [
            "Baseline should sit near mid-supply (~1635 mV).",
            "Check electrode placement and that the reference is attached.",
        ]
    if not (GOOD_PP_MV[0] <= h["pp_mv"] <= GOOD_PP_MV[1]):
        if h["pp_mv"] < GOOD_PP_MV[0]:
            return "VERY QUIET - weak contact", ["Clean the skin with alcohol and let it dry; check for hair under the pad."]
        return "LOUD - louder than the good reference batch", ["Sit still and re-run; if it persists, treat as interference."]
    return "OK - looks like the good 2026-08-26 batch", []


def main():
    ap = argparse.ArgumentParser(description="Check for mains interference / bad electrode contact")
    ap.add_argument("--port", help="COM port (e.g. COM5). Auto-detects if omitted.")
    ap.add_argument("--seconds", type=float, default=4.0, help="Capture duration")
    ap.add_argument("--mains", type=float, default=50.0, help="Mains frequency (50 in India/EU, 60 in US)")
    ap.add_argument("--list", action="store_true", help="List serial ports and exit")
    args = ap.parse_args()

    if args.list:
        for p in EMGSerialReader.list_ports():
            print(" ", p)
        return

    port = args.port
    if not port:
        ports = EMGSerialReader.list_ports()
        if not ports:
            print("ERROR: no serial ports found. Connect the ESP32.")
            sys.exit(1)
        port = ports[0] if isinstance(ports[0], str) else ports[0].device
        print(f"Auto-selected port: {port}")

    print(f"Sit still and do NOT articulate -- measuring the noise floor for {args.seconds:.0f}s...")
    reader = EMGSerialReader(port, baud_rate=921600, num_channels=1)
    reader.connect()
    result = reader.read_samples(args.seconds)
    try:
        reader.close()
    except Exception:
        pass

    channels = result["channels"]
    if len(channels) == 0:
        print("ERROR: no samples captured. Is another program holding the port?")
        sys.exit(1)
    counts = channels[:, 0]

    r = analyse(counts, FS_DEFAULT, args.mains)
    h = r["health"]
    m = int(args.mains)

    print()
    print("=" * 62)
    print(f"  samples          {len(counts)}")
    print(f"  baseline         {h['baseline_mv']:.1f} mV      (healthy ~1635, range 935..2335)")
    print(f"  peak-to-peak     {h['pp_mv']:.1f} mV      (good batch: 56..498, median 217)")
    print(f"  counts           {r['min_counts']:.0f} .. {r['max_counts']:.0f}   (rail is 0 .. ~26500)")
    print("  " + "-" * 58)
    print(f"  power at {m} Hz    {r['mains']:6.1%}        (good batch: 3.7%)")
    print(f"  power at {2*m} Hz   {r['harmonic']:6.1%}")
    print(f"  power 20-200 Hz  {r['emg']:6.1%}")
    print(f"  power 0.1-5 Hz   {r['drift']:6.1%}        (good batch: ~70%, envelope-dominated)")
    print("=" * 62)

    headline, actions = verdict(r)
    print(f"\n  VERDICT: {headline}\n")
    for a in actions:
        print(f"    - {a}")
    if actions:
        print("\n  Re-run this after each change; you want 50 Hz power back under 15%.")
    print()


if __name__ == "__main__":
    main()
