#!/usr/bin/env python3
"""
VA Visualizer — CLI entry point.

Usage:
  python -m visualization.visualize <file.vams> [options]
  python -m visualization.visualize --demo
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from .parser import parse_file, parse_source
from .renderer import render_html
from .launcher import open_in_browser, browser_info


# ── Demo Verilog-A source ────────────────────────────────────────────────────

_DEMO_SOURCE = """\
// Verilog-A demo: VCSEL laser model
`include "disciplines.vams"
`include "constants.vams"

module vcsel(anode, cathode, optical_out);
  inout electrical anode, cathode;
  output electrical optical_out;

  parameter real I_th  = 5e-3   from (0:inf);   // threshold current (A)
  parameter real eta   = 0.5    from (0:1];      // slope efficiency (W/A)
  parameter real R_s   = 5.0    from (0:inf);    // series resistance (Ohm)
  parameter real C_j   = 10e-12 from (0:inf);    // junction capacitance (F)
  parameter real tau_r = 1e-9   from (0:inf);    // photon lifetime (s)

  electrical int_node;
  branch (anode,   int_node)  b_rs;
  branch (int_node, cathode)  b_junc;

  analog begin
    // Resistive series drop
    V(b_rs) <+ R_s * I(b_rs);

    // Junction voltage-current: laser diode model
    I(b_junc) <+ I_th * (limexp(V(b_junc)/(`P_Q*300/`P_K)) - 1.0);

    // Capacitive displacement current
    I(b_junc) <+ C_j * ddt(V(b_junc));

    // Optical output power
    V(optical_out) <+ eta * max(I(b_junc) - I_th, 0.0) * tau_r;
  end
endmodule


// Simple passive resistor model
module resistor(p, n);
  inout electrical p, n;

  parameter real R = 1e3 from (0:inf);
  parameter real TC1 = 0.0;
  parameter real TC2 = 0.0;
  parameter real TNOM = 27.0;

  branch (p, n) res;

  analog begin
    V(res) <+ R * (1.0 + TC1*(($temperature-TNOM)) + TC2*(($temperature-TNOM)**2)) * I(res);
  end
endmodule


// Voltage-controlled current source
module vccs(inp, inn, outp, outn);
  input  electrical inp, inn;
  output electrical outp, outn;

  parameter real Gm = 1e-3 from (0:inf);   // transconductance (S)
  parameter real Rout = 1e9;                // output resistance (Ohm)

  branch (outp, outn) b_out;

  analog begin
    I(b_out) <+ Gm * V(inp, inn);
    I(b_out) <+ V(b_out) / Rout;
  end
endmodule
"""


# ── Core API ─────────────────────────────────────────────────────────────────

def visualize(
    filepath: str = None,
    source: str = None,
    browser: str = 'auto',
    use_profile: bool = True,
    output: str = None,
    quiet: bool = False,
) -> str:
    """
    Parse a Verilog-A file (or source string) and open it in the browser.

    Returns the path to the generated HTML file.
    """
    def log(msg):
        if not quiet:
            print(msg)

    if filepath:
        filepath = os.path.abspath(filepath)
        log(f"Parsing  : {filepath}")
        modules = parse_file(filepath)
        with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
            source = fh.read()
        label = Path(filepath).name
    elif source:
        modules = parse_source(source)
        filepath = ''
        label = 'source'
    else:
        raise ValueError("Provide either filepath or source.")

    if not modules:
        log("Warning  : No `module … endmodule` blocks found.")
    else:
        names = ', '.join(m.name for m in modules)
        log(f"Found    : {len(modules)} module(s) — {names}")

    html = render_html(modules, source, filepath)

    if output:
        out_path = os.path.abspath(output)
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write(html)
    else:
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.html',
            prefix=f'va_viz_{Path(filepath).stem if filepath else label}_',
            delete=False, encoding='utf-8',
        )
        out_path = tmp.name
        tmp.write(html)
        tmp.close()

    log(f"Generated: {out_path}")

    ok = open_in_browser(out_path, browser=browser, use_profile=use_profile)
    if ok:
        log(f"Opened   : browser={browser}, profile={'yes' if use_profile else 'no'}")
    else:
        log(f"No browser found. Open manually:\n  file://{out_path}")

    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='va-visualize',
        description='Visualise a Verilog-A file in Chrome or Firefox.',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        'file', nargs='?',
        help='Path to the Verilog-A file (.va, .vams, .verilog, .scs, ...)',
    )
    p.add_argument(
        '--demo', action='store_true',
        help='Run with a built-in VCSEL / resistor / VCCS demo.',
    )
    p.add_argument(
        '--browser', choices=['auto', 'chrome', 'firefox'], default='auto',
        help='Browser to use (default: auto — tries Chrome then Firefox).',
    )
    p.add_argument(
        '--no-profile', action='store_true',
        help="Don't pass the user's existing browser profile.",
    )
    p.add_argument(
        '--output', '-o', metavar='FILE',
        help='Save the HTML to this path instead of a temp file.',
    )
    p.add_argument(
        '--info', action='store_true',
        help='Show detected browsers and profiles, then exit.',
    )
    p.add_argument(
        '--quiet', '-q', action='store_true',
        help='Suppress informational output.',
    )
    return p


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.info:
        info = browser_info()
        print("Browser detection results:")
        print(f"  Chrome   : {info['chrome'] or 'not found'}")
        print(f"  Firefox  : {info['firefox'] or 'not found'}")
        print(f"  Chrome profile dir  : {info['chrome_profile'] or 'not found'}")
        print(f"  Firefox profile dir : {info['firefox_profile'] or 'not found'}")
        return

    if args.demo:
        visualize(
            source=_DEMO_SOURCE,
            browser=args.browser,
            use_profile=not args.no_profile,
            output=args.output,
            quiet=args.quiet,
        )
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    visualize(
        filepath=args.file,
        browser=args.browser,
        use_profile=not args.no_profile,
        output=args.output,
        quiet=args.quiet,
    )


if __name__ == '__main__':
    main()
