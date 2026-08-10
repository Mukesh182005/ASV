"""
ASV — Live EMG Plotter
======================
Usage:
    # Live view from ESP32 (close Arduino IDE Serial Monitor first!)
    python tools/plot_emg.py --port COM8

    # Plot a saved CSV
    python tools/plot_emg.py --file test.csv

    # Live view with wider window
    python tools/plot_emg.py --port COM8 --window 5
"""

import argparse
import sys
import time
import collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

UV_PER_LSB = 125.0          # gain index 1 default (+/-4.096V)
SAMPLING_RATE = 860

def counts_to_mv(counts):
    return (counts * UV_PER_LSB) / 1000.0

# ─── LIVE MODE ─────────────────────────────────────────────────────────────────

def run_live(port, window_sec=4):
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    print(f"Opening {port} at 921600 baud...")
    try:
        ser = serial.Serial(port, 921600, timeout=1)
    except Exception as e:
        print(f"ERROR: {e}")
        print("Close Arduino IDE Serial Monitor first!")
        sys.exit(1)

    # flush & send start command
    time.sleep(0.5)
    ser.reset_input_buffer()
    ser.write(b's')

    buf_size = int(SAMPLING_RATE * window_sec)
    times  = collections.deque([0.0] * buf_size, maxlen=buf_size)
    values = collections.deque([0.0] * buf_size, maxlen=buf_size)

    fig, (ax_raw, ax_info) = plt.subplots(2, 1, figsize=(12, 6),
                                          gridspec_kw={'height_ratios': [4, 1]})
    fig.suptitle('ASV — Live EMG  (close window to stop)', fontsize=13, fontweight='bold')
    fig.patch.set_facecolor('#0f0f1a')
    for ax in (ax_raw, ax_info):
        ax.set_facecolor('#0f0f1a')
        ax.tick_params(colors='#aaaaaa')
        for spine in ax.spines.values():
            spine.set_color('#333355')

    line_raw, = ax_raw.plot([], [], color='#00e5ff', linewidth=0.8, alpha=0.9)
    ax_raw.set_ylabel('mV', color='#aaaaaa')
    ax_raw.set_xlabel('time (s)', color='#aaaaaa')
    ax_raw.set_xlim(0, window_sec)
    ax_raw.set_ylim(-200, 3500)
    ax_raw.axhline(1635, color='#ff6b35', linewidth=0.6, linestyle='--', label='expected baseline ~1635mV')
    ax_raw.legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', labelcolor='#aaaaaa')
    ax_raw.grid(True, color='#222244', linewidth=0.4)

    info_text = ax_info.text(0.01, 0.5, '', transform=ax_info.transAxes,
                              color='#00e5ff', fontsize=9, va='center', fontfamily='monospace')
    ax_info.axis('off')

    t0 = None
    stats = {'rate': 0, 'baseline': 0, 'pp': 0, 'lo': '?/?', 'drops': 0}
    sample_count = [0]
    last_stat_time = [time.time()]

    line_buf = b''

    def parse_serial():
        nonlocal line_buf, t0
        chunk = ser.read(ser.in_waiting or 1)
        if not chunk:
            return
        line_buf += chunk
        while b'\n' in line_buf:
            raw, line_buf = line_buf.split(b'\n', 1)
            raw = raw.strip()
            if not raw or raw.startswith(b'#') or raw.startswith(b'-') or raw.startswith(b'['):
                continue
            try:
                parts = raw.decode('ascii', errors='ignore').split(',')
                if len(parts) >= 2:
                    ts_us = int(parts[0])
                    ch0   = int(parts[1])
                    if t0 is None:
                        t0 = ts_us
                    t_rel = (ts_us - t0) / 1e6
                    mv    = counts_to_mv(ch0)
                    times.append(t_rel)
                    values.append(mv)
                    sample_count[0] += 1
            except Exception:
                pass

    def update(frame):
        parse_serial()
        now = time.time()
        elapsed = now - last_stat_time[0]
        if elapsed >= 1.0:
            stats['rate'] = sample_count[0] / elapsed
            sample_count[0] = 0
            last_stat_time[0] = now

        arr = np.array(values)
        t_arr = np.array(times)

        if len(arr) > 1:
            mv_arr = arr
            stats['baseline'] = float(np.mean(mv_arr[-SAMPLING_RATE:]))
            stats['pp']       = float(np.ptp(mv_arr[-SAMPLING_RATE:]))
            t_end = t_arr[-1]
            t_start = max(t_end - window_sec, 0)
            mask = t_arr >= t_start
            line_raw.set_data(t_arr[mask] - t_start, mv_arr[mask])
            ax_raw.set_xlim(0, window_sec)
            auto_min = max(-200, stats['baseline'] - max(500, stats['pp'] * 1.5))
            auto_max = stats['baseline'] + max(500, stats['pp'] * 1.5)
            ax_raw.set_ylim(auto_min, auto_max)

        status = '[FLAT - OUTPUT->A0 wire missing!]' if stats['baseline'] < 10 else '[Signal OK]'
        info_text.set_text(
            f"rate={stats['rate']:.0f} Hz | "
            f"baseline={stats['baseline']:.1f} mV  |  "
            f"peak-to-peak={stats['pp']:.1f} mV  |  "
            f"{status}"
        )
        return line_raw, info_text

    ani = animation.FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()
    ser.write(b'x')
    ser.close()
    print("Stream stopped.")


# ─── FILE MODE ─────────────────────────────────────────────────────────────────

def run_file(filepath):
    import pandas as pd

    df = pd.read_csv(filepath)
    ts_col  = df.columns[0]  # timestamp_us
    ch_col  = df.columns[1]  # channel_0

    t  = (df[ts_col].values - df[ts_col].values[0]) / 1e6
    mv = df[ch_col].values * UV_PER_LSB / 1000.0

    baseline = np.mean(mv)
    pp       = np.ptp(mv)
    n        = len(mv)
    duration = t[-1] - t[0]
    rate     = n / duration if duration > 0 else 0

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor('#0f0f1a')
    ax.set_facecolor('#0f0f1a')
    ax.tick_params(colors='#aaaaaa')
    for spine in ax.spines.values():
        spine.set_color('#333355')

    ax.plot(t, mv, color='#00e5ff', linewidth=0.6, alpha=0.85, label='EMG channel 0')
    ax.axhline(baseline, color='#ff6b35', linewidth=1, linestyle='--',
               label=f'baseline = {baseline:.1f} mV')
    ax.set_xlabel('time (s)', color='#aaaaaa')
    ax.set_ylabel('mV', color='#aaaaaa')

    status = '[FLAT - OUTPUT->A0 wire not connected]' if baseline < 10 else '[Signal present]'
    ax.set_title(
        f'ASV EMG — {Path(filepath).name}  |  '
        f'{n} samples  |  {rate:.0f} Hz  |  '
        f'baseline={baseline:.1f} mV  |  pp={pp:.2f} mV  |  {status}',
        color='#dddddd', fontsize=10
    )
    ax.legend(facecolor='#1a1a2e', labelcolor='#aaaaaa', fontsize=9)
    ax.grid(True, color='#222244', linewidth=0.4)
    plt.tight_layout()

    outfile = Path(filepath).with_suffix('.png')
    plt.savefig(outfile, dpi=150, facecolor='#0f0f1a')
    print(f"Saved plot -> {outfile}")
    plt.show()


# --- MAIN ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='ASV EMG Plotter')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--port',   help='COM port for live view (e.g. COM8)')
    group.add_argument('--file',   help='CSV file to plot')
    parser.add_argument('--window', type=float, default=4.0,
                        help='Live view time window in seconds (default 4)')
    args = parser.parse_args()

    if args.file:
        run_file(args.file)
    else:
        run_live(args.port, args.window)

if __name__ == '__main__':
    main()
