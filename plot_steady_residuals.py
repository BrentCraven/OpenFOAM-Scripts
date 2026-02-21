#!/usr/bin/env python3

"""
plot_steady_residuals.py logfile: Parse OpenFOAM log file ('logfile') from simpleFoam and plot residuals

options:
  -h, --help           show this help message and exit
  --out OUT            Output image path
  --csv CSV            Optional CSV export path
  --watch              Watch the log file and update the plot in real-time
  --interval INTERVAL  Refresh interval in seconds for --watch (default: 1)

USAGE:
  # Make executable
  chmod +x plot_steady_residuals.py

  # Show plot interactively and update in real-time (no file written)
  ./plot_steady_residuals.py log.simpleFoam --watch

  # Save plot to file with no interactive plot (format inferred from extension)
  ./plot_steady_residuals.py log.simpleFoam --out residuals.png
  ./plot_steady_residuals.py log.simpleFoam --out residuals.pdf
  ./plot_steady_residuals.py log.simpleFoam --out residuals.svg

  # Optional CSV export of residuals
  ./plot_steady_residuals.py log.simpleFoam --out residuals.png --csv residuals.csv

NOTES:
  - Y-axis is logarithmic; non-positives are masked to NaN to avoid log errors.
"""

import argparse
import re
import math
import sys
import csv
import time
from typing import List, Tuple, Optional, Dict

import matplotlib.pyplot as plt

def parse_log(log_path: str) -> Tuple[List[Dict], List[str]]:
    """Parse OpenFOAM log for all residuals and return (rows, found_keys)."""
    res_re = re.compile(r'Solving\s+for\s+(?P<var>\w+),\s*Initial\s+residual\s*=\s*(?P<val>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)')
    time_re = re.compile(r'^\s*Time\s*=\s*(?P<time>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$')
    end_re  = re.compile(r'^\s*ExecutionTime\b')

    rows = []
    current_row = {}
    found_keys = set()

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m_time = time_re.search(line)
                if m_time:
                    if current_row and 'Time' in current_row:
                        rows.append(current_row)
                    current_row = {'Time': float(m_time.group('time'))}
                    continue

                m_res = res_re.search(line)
                if m_res:
                    var = m_res.group('var')
                    if var not in current_row:
                        val = float(m_res.group('val'))
                        current_row[var] = val
                        found_keys.add(var)
                    continue

                if end_re.search(line):
                    if current_row and 'Time' in current_row:
                        rows.append(current_row)
                    current_row = {}

        if current_row and 'Time' in current_row:
            rows.append(current_row)
    except FileNotFoundError:
        return [], []

    rows.sort(key=lambda r: r['Time'])
    
    priority = ['Ux', 'Uy', 'Uz', 'p', 'k', 'omega', 'epsilon', 'nut', 'nuTilda']
    sorted_keys = [k for k in priority if k in found_keys]
    sorted_keys += sorted([k for k in found_keys if k not in priority])
    
    return rows, sorted_keys

def write_csv(rows: List[Dict], keys: List[str], csv_path: str) -> None:
    """Write CSV with Time and all detected residual columns."""
    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['Time'] + keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def mask_nonpositive(series: List[float]) -> List[float]:
    return [v if (v is not None and v > 0.0) else math.nan for v in series]

def update_plot(ax, rows, keys):
    """Refreshes the data on the provided axes."""
    ax.clear()
    ax.set_yscale('log')
    
    if not rows:
        return

    times = [r['Time'] for r in rows]
    for var in keys:
        data = [r.get(var) for r in rows]
        masked_data = mask_nonpositive(data)
        
        lw = 2.0 if var in ['p', 'Ux', 'Uy', 'Uz'] else 1.5
        ax.plot(times, masked_data, label=var, linewidth=lw, linestyle='-')

    ax.set_xlim(0, max(times))
    ax.set_xlabel('Iteration', fontweight='bold')
    ax.set_ylabel('Residual', fontweight='bold')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(loc='upper right', frameon=True, ncol=2)
    plt.title(f"Residuals", fontweight='bold')

def main() -> None:
    ap = argparse.ArgumentParser(description="Parse OpenFOAM log and plot residuals.")
    ap.add_argument('logfile', help="Path to OpenFOAM log file")
    ap.add_argument('--out', default=None, help="Output image path.")
    ap.add_argument('--csv', default=None, help="Optional CSV export path.")
    ap.add_argument('--watch', action='store_true', help="Watch the log file and update the plot in real-time.")
    ap.add_argument('--interval', type=int, default=1, help="Refresh interval in seconds for --watch (default: 1).")
    args = ap.parse_args()

    if args.watch:
        plt.ion() # Enable interactive mode
        fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
        
        print(f"Watching {args.logfile}. Press Ctrl+C to stop.")
        try:
            while True:
                rows, keys = parse_log(args.logfile)
                if rows:
                    update_plot(ax, rows, keys)
                    plt.draw()
                    plt.pause(args.interval)
                    if args.csv:
                        write_csv(rows, keys, args.csv)
                else:
                    print("Waiting for data...")
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nWatch stopped by user.")
            if args.out:
                fig.savefig(args.out, dpi=200)
    else:
        # Standard one-time execution
        rows, keys = parse_log(args.logfile)
        if args.csv:
            write_csv(rows, keys, args.csv)
        
        fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
        update_plot(ax, rows, keys)
        
        if args.out:
            fig.savefig(args.out, dpi=200)
        else:
            plt.show()

if __name__ == '__main__':
    main()
