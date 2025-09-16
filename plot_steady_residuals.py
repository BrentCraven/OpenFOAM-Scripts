#!/usr/bin/env python3

"""
plot_steady_residuals.py: Parse OpenFOAM log file from simpleFoam and plot residuals for Ux, Uy, Uz (if present), and p

USAGE:
  # Make executable
  chmod +x plot_steady_residuals.py

  # Show plot interactively (no file written)
  ./plot_steady_residuals.py log.simpleFoam

  # Save plot to file with no interactive plot (format inferred from extension)
  ./plot_steady_residuals.py log.simpleFoam --out residuals.png
  ./plot_steady_residuals.py log.simpleFoam --out residuals.pdf
  ./plot_steady_residuals.py log.simpleFoam --out residuals.svg

  # Optional CSV export (columns: Time, Ux residual, Uy residual, Uz residual (if present), p residual)
  ./plot_steady_residuals.py log.simpleFoam --out residuals.png --csv residuals.csv

NOTES:
  - Y-axis is logarithmic; non-positives are masked to NaN to avoid log errors.
"""

import argparse  # Parse command-line arguments
import re        # Regular expressions for parsing log lines
import math      # Provides math.nan and numeric checks
import sys       # For clean process termination with messages
from typing import List, Tuple, Optional  # Type hints for clarity

import matplotlib.pyplot as plt  # Plotting backend (save/show figures)


def parse_log(log_path: str) -> Tuple[List[Tuple[float, float, float, float, float]], bool]:
    """Return (rows, has_uz) where rows are (time, Ux, Uy, p, Uz)."""  # Describe output schema
    time_re = re.compile(r'^\s*Time\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$')  # Match 'Time = <num>'
    ux_re   = re.compile(r'Solving\s+for\s+Ux,\s*Initial\s+residual\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)')  # Ux initial
    uy_re   = re.compile(r'Solving\s+for\s+Uy,\s*Initial\s+residual\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)')  # Uy initial
    uz_re   = re.compile(r'Solving\s+for\s+Uz,\s*Initial\s+residual\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)')  # Uz initial
    p_re    = re.compile(r'Solving\s+for\s+p,\s*Initial\s+residual\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)')   # p  initial
    end_re  = re.compile(r'^\s*ExecutionTime\b')  # Block terminator line in OpenFOAM logs

    current_time = None        # Active block time marker
    ux_init = math.nan         # Ux initial residual accumulator for block
    uy_init = math.nan         # Uy initial residual accumulator for block
    uz_init = math.nan         # Uz initial residual accumulator for block
    p_init  = math.nan         # p  initial residual accumulator for block

    has_uz = False             # Whether Uz appears in any block
    rows: List[Tuple[float, float, float, float, float]] = []  # Accumulator of (time, Ux, Uy, p, Uz)

    with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:  # Stream file to handle large logs
        for line in fh:  # Iterate lines
            m_time = time_re.search(line)  # Detect 'Time = ...'
            if m_time:  # Start of a new block
                if current_time is not None:  # Flush previous block if open
                    rows.append((current_time, ux_init, uy_init, p_init, uz_init))  # Append row
                current_time = float(m_time.group(1))  # Set time for new block
                ux_init = uy_init = uz_init = p_init = math.nan  # Reset block accumulators
                continue  # Next line

            if current_time is not None:  # Only parse residuals within a time block
                if math.isnan(ux_init):  # Capture first Ux initial residual in this block
                    m_ux = ux_re.search(line)  # Try matching Ux
                    if m_ux:
                        ux_init = float(m_ux.group(1))  # Store Ux initial residual
                        continue  # Next line

                if math.isnan(uy_init):  # Capture first Uy initial residual in this block
                    m_uy = uy_re.search(line)  # Try matching Uy
                    if m_uy:
                        uy_init = float(m_uy.group(1))  # Store Uy initial residual
                        continue  # Next line

                if math.isnan(uz_init):  # Capture first Uz initial residual in this block
                    m_uz = uz_re.search(line)  # Try matching Uz
                    if m_uz:
                        uz_init = float(m_uz.group(1))  # Store Uz initial residual
                        has_uz = True  # Flag presence of Uz in the log
                        continue  # Next line

                if math.isnan(p_init):  # Capture first p initial residual in this block
                    m_p = p_re.search(line)  # Try matching p
                    if m_p:
                        p_init = float(m_p.group(1))  # Store p initial residual
                        continue  # Next line

                if end_re.search(line):  # End-of-block marker
                    rows.append((current_time, ux_init, uy_init, p_init, uz_init))  # Append row
                    current_time = None  # Clear block state
                    ux_init = uy_init = uz_init = p_init = math.nan  # Reset accumulators
                    continue  # Next line

    if current_time is not None:  # Flush trailing block missing ExecutionTime
        rows.append((current_time, ux_init, uy_init, p_init, uz_init))  # Append last row

    rows.sort(key=lambda r: r[0])  # Sort rows by time ascending
    return rows, has_uz  # Return the parsed table and Uz presence flag


def write_csv(rows: List[Tuple[float, float, float, float, float]], csv_path: str, has_uz: bool) -> None:
    """Write CSV with columns: Time, Ux residual, Uy residual, [Uz residual], p residual (order enforced)."""  # CSV schema
    import csv  # Lazy import for CSV I/O
    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:  # Open destination CSV
        w = csv.writer(fh)  # CSV writer
        header = ['Time', 'Ux residual', 'Uy residual']  # Start header with Ux, Uy
        if has_uz:  # Include Uz if present
            header.append('Uz residual')  # Add Uz column
        header.append('p residual')  # p always last
        w.writerow(header)  # Write header row
        for t, ux, uy, p, uz in rows:  # Iterate parsed rows
            if has_uz:  # Five-field case
                w.writerow([t, ux, uy, uz, p])  # Order: Ux, Uy, Uz, p
            else:  # Four-field case
                w.writerow([t, ux, uy, p])  # Order: Ux, Uy, p


def mask_nonpositive(series: List[float]) -> List[float]:
    """Map v<=0 to NaN for log-scale safety."""  # Explain masking
    return [v if (isinstance(v, (float, int)) and v > 0.0) else math.nan for v in series]  # Replace non-positives


def plot(rows: List[Tuple[float, float, float, float, float]], out_path: Optional[str], has_uz: bool) -> None:
    """Plot residuals in order Ux, Uy, Uz?, p; bold axis labels; save or show."""  # Plot behavior
    if not rows:  # Guard against empty input
        sys.exit("No residual records found in the log.")  # Abort with message

    times = [r[0] for r in rows]  # X-axis values (time)
    ux    = [r[1] for r in rows]  # Ux series
    uy    = [r[2] for r in rows]  # Uy series
    p     = [r[3] for r in rows]  # p series
    uz    = [r[4] for r in rows]  # Uz series (may be all-NaN)

    ux_m = mask_nonpositive(ux)  # Mask non-positives for log-scale
    uy_m = mask_nonpositive(uy)  # Mask non-positives for log-scale
    uz_m = mask_nonpositive(uz) if has_uz else None  # Mask Uz if present
    p_m  = mask_nonpositive(p)   # Mask non-positives for log-scale

    fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)  # Figure with tight layout
    ax.set_yscale('log')  # Logarithmic Y-axis to visualize decades

    # All lines use linestyle='-' as requested
    ax.plot(times, ux_m, label='Ux', linewidth=2.0, linestyle='-')  # Ux (solid)
    ax.plot(times, uy_m, label='Uy', linewidth=2.0, linestyle='-')  # Uy (solid)
    if has_uz:  # Conditionally include Uz
        ax.plot(times, uz_m, label='Uz', linewidth=2.0, linestyle='-')  # Uz (solid)
    ax.plot(times, p_m,  label='p',  linewidth=2.0, linestyle='-')  # p (solid)

    tmax = max(t for t in times if isinstance(t, (int, float)))
    ax.set_xlim(0, tmax)  # x range [0, tmax]

    ax.set_xlabel('Time', fontweight='bold')               # Bold X-axis label
    ax.set_ylabel('Residual', fontweight='bold')   # Bold Y-axis label
    ax.grid(True, which='both', alpha=0.3)                 # Light grid on major/minor ticks
    ax.legend(loc='upper right', frameon=True)             # Legend placement and frame

    if out_path:  # Save if output path provided
        fig.savefig(out_path, dpi=200)  # Save figure; format inferred by extension
    else:  # Otherwise show interactively
        plt.show()  # Open GUI window


def main() -> None:
    """CLI: parse args, parse log, optional CSV, then plot (save or show)."""  # Entry point description
    ap = argparse.ArgumentParser(description="Parse OpenFOAM log and plot initial residuals for Ux, Uy, Uz (if present), and p.")  # CLI parser
    ap.add_argument('logfile', help="Path to OpenFOAM-style log.simpleFoam (e.g., log.simpleFoam)")  # Positional logfile path
    ap.add_argument('--out', default=None, help="Output image path (.png/.pdf/.svg). If omitted, shows interactively.")  # Optional output
    ap.add_argument('--csv', default=None, help="Optional CSV export path (columns: Time, Ux, Uy, [Uz], p)")  # Optional CSV path
    args = ap.parse_args()  # Parse arguments

    rows, has_uz = parse_log(args.logfile)  # Parse the log and detect Uz presence
    if args.csv:  # CSV export requested
        write_csv(rows, args.csv, has_uz)  # Write CSV file
    plot(rows, args.out, has_uz)  # Render plot and either save or show


if __name__ == '__main__':  # Script entry guard
    main()  # Execute CLI workflow

