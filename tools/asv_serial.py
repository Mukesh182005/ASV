#!/usr/bin/env python3
"""Scriptable serial harness for the ASV firmware.

`arduino-cli monitor` is interactive and never returns, which makes it useless
for automation. This tool sends a firmware command, captures output for a fixed
window, prints it, and exits with a meaningful status code.

Examples
--------
    python tools/asv_serial.py --list
    python tools/asv_serial.py --port COM3 --cmd t --seconds 10
    python tools/asv_serial.py --port COM3 --check          # self-test, exit 1 on failure
    python tools/asv_serial.py --port COM3 --cmd n --seconds 6
    python tools/asv_serial.py --port COM3 --stream --seconds 5 --out probe.csv

Exit codes
----------
    0  success
    1  failure (self-test failed, no samples, bad stream)
    2  could not open the port
"""
import argparse
import sys
import time
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial is not installed.  Run:  python -m pip install pyserial",
          file=sys.stderr)
    sys.exit(2)

DEFAULT_BAUD = 921600
PASS_MARKER = "RESULT: ALL CHECKS PASSED"
FAIL_MARKER = "RESULT: PROBLEMS FOUND"


# ---------------------------------------------------------------------------
def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found. Is the ESP32 plugged in?")
        return 1
    print(f"{'PORT':<12} {'DESCRIPTION':<40} HWID")
    for p in ports:
        print(f"{p.device:<12} {(p.description or ''):<40} {p.hwid or ''}")
    return 0


def open_port(port, baud, reset_wait):
    try:
        conn = serial.Serial(port, baud, timeout=0.2)
    except serial.SerialException as e:
        print(f"ERROR: cannot open {port}: {e}", file=sys.stderr)
        print("       Another program may hold the port - close the Arduino IDE",
              file=sys.stderr)
        print("       Serial Monitor, or any other script using it.", file=sys.stderr)
        return None
    # Opening the port pulls DTR/RTS and resets the ESP32.
    if reset_wait > 0:
        time.sleep(reset_wait)
    conn.reset_input_buffer()
    return conn


def capture(conn, seconds, echo=True):
    """Read lines for `seconds`, optionally echoing them. Returns the list."""
    lines = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        raw = conn.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(text)
        if echo:
            print(text)
    return lines


# ---------------------------------------------------------------------------
def cmd_send(args):
    conn = open_port(args.port, args.baud, args.reset_wait)
    if conn is None:
        return 2
    try:
        conn.write(b"x")          # leave any stream/monitor mode first
        time.sleep(0.2)
        conn.reset_input_buffer()
        conn.write(args.cmd.encode())
        print(f"--- sent '{args.cmd}', capturing {args.seconds}s from {args.port} ---\n")
        lines = capture(conn, args.seconds)
    finally:
        try:
            conn.write(b"x")
        except serial.SerialException:
            pass
        conn.close()

    if not lines:
        print("\nERROR: no output received.", file=sys.stderr)
        print("       Check the baud rate (should be 921600) and that the board is running.",
              file=sys.stderr)
        return 1

    blob = "\n".join(lines)
    if args.cmd in ("t", "T") or args.check:
        if PASS_MARKER in blob:
            print("\n>>> SELF-TEST PASSED")
            return 0
        if FAIL_MARKER in blob:
            print("\n>>> SELF-TEST FAILED - see the [FAIL] lines above", file=sys.stderr)
            return 1
        print("\n>>> SELF-TEST INCONCLUSIVE - no result line seen.", file=sys.stderr)
        print("    Try a longer --seconds (the test takes ~5s).", file=sys.stderr)
        return 1
    return 0


def cmd_stream(args):
    conn = open_port(args.port, args.baud, args.reset_wait)
    if conn is None:
        return 2

    header = {}
    samples = []
    try:
        conn.write(b"x")
        time.sleep(0.2)
        conn.reset_input_buffer()
        conn.write(b"s")

        # Wait for the firmware's stream header.
        started = False
        deadline = time.time() + 5
        while time.time() < deadline and not started:
            raw = conn.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("# ASV_STREAM"):
                for tok in line.replace("# ASV_STREAM", "").split():
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        header[k] = v
            if line.startswith("--- START DATA ---"):
                started = True

        if not started:
            print("WARNING: never saw '--- START DATA ---'. Capturing anyway.",
                  file=sys.stderr)

        deadline = time.time() + args.seconds
        while time.time() < deadline:
            raw = conn.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or not line[0].isdigit():
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                samples.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
    finally:
        try:
            conn.write(b"x")
        except serial.SerialException:
            pass
        conn.close()

    if header:
        print("firmware header:", header)

    if len(samples) < 2:
        print(f"ERROR: captured {len(samples)} samples - the stream is not running.",
              file=sys.stderr)
        return 1

    ts = [s[0] for s in samples]
    vs = [s[1] for s in samples]
    unit = header.get("ts_unit", "us")
    per_second = 1e6 if unit == "us" else 1e3

    dts = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    dts = [d for d in dts if d > 0]
    if not dts:
        print("ERROR: timestamps are not monotonic.", file=sys.stderr)
        return 1

    mean_dt = sum(dts) / len(dts)
    var = sum((d - mean_dt) ** 2 for d in dts) / len(dts)
    std_dt = var ** 0.5
    rate = per_second / mean_dt
    jitter_ratio = std_dt / mean_dt if mean_dt else 0

    uv_per_lsb = float(header.get("uv_per_lsb", 125.0))
    mean_counts = sum(vs) / len(vs)

    print()
    print(f"samples      : {len(samples)}")
    print(f"rate         : {rate:.2f} Hz")
    print(f"dt mean/std  : {mean_dt:.1f} / {std_dt:.1f} {unit}   (jitter ratio {jitter_ratio:.3f})")
    print(f"dt min/max   : {min(dts)} / {max(dts)} {unit}")
    print(f"baseline     : {mean_counts:.0f} counts = {mean_counts * uv_per_lsb / 1000:.1f} mV")
    print(f"min/max      : {min(vs)} / {max(vs)} counts")
    print(f"peak-to-peak : {(max(vs) - min(vs)) * uv_per_lsb / 1000:.2f} mV")

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as fh:
            fh.write(f"timestamp_{unit},channel_0\n")
            for t, v in samples:
                fh.write(f"{t},{v}\n")
        print(f"\nwrote {path}  ({len(samples)} rows)")

    status = 0
    if jitter_ratio > 0.25:
        print("\nWARNING: high timing jitter. Is the ADS1115 ALRT wire on GPIO27?",
              file=sys.stderr)
        status = 1
    expected = float(header.get("fs", 860))
    if abs(rate - expected) / expected > 0.15:
        print(f"WARNING: rate {rate:.1f} Hz differs >15% from firmware target {expected:.0f} Hz.",
              file=sys.stderr)
        status = 1
    return status


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Scriptable serial harness for ASV firmware",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    ap.add_argument("--port", help="serial port, e.g. COM3 or /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--cmd", help="firmware command letter: t i n m s x g o r ?")
    ap.add_argument("--check", action="store_true",
                    help="run the self-test and exit non-zero unless it passes")
    ap.add_argument("--stream", action="store_true",
                    help="capture the raw CSV stream and report timing quality")
    ap.add_argument("--seconds", type=float, default=8.0, help="capture window")
    ap.add_argument("--out", help="write captured stream to this CSV path")
    ap.add_argument("--reset-wait", type=float, default=2.0,
                    help="seconds to wait after opening the port (ESP32 resets)")
    args = ap.parse_args()

    if args.list:
        return list_ports()

    if not args.port:
        print("ERROR: --port is required (or use --list to find one).", file=sys.stderr)
        return 2

    if args.stream:
        return cmd_stream(args)

    if args.check and not args.cmd:
        args.cmd = "t"
        args.seconds = max(args.seconds, 10.0)

    if not args.cmd:
        print("ERROR: give --cmd, --stream, or --check.", file=sys.stderr)
        return 2

    return cmd_send(args)


if __name__ == "__main__":
    sys.exit(main())
