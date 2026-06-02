"""Operational CLI for the ballast portfolio maintenance toolkit.

    python -m ballast.portfolio setup   --total 300000 [--price P]
    python -m ballast.portfolio check    [--lot N --price P --cash C]
    python -m ballast.portfolio report   [--no-write]

Computes target lot sizes, band-rebalance direction, and periodic reports.
It NEVER executes trades - output is the action to perform manually in the broker.
When --price is omitted, the live ZPX30 price is fetched; when check args are
omitted, holdings are read from the (git-ignored) portfoy_state.json.
"""
from __future__ import annotations

import argparse
import sys

from ballast.portfolio.rebalance_check import BANT, HEDEF_ORAN, rebalance_kontrol
from ballast.portfolio.setup_calculator import (
    HEDEF_BORSA_ORAN,
    ZPX30_SYMBOL,
    hesapla_ilk_portfoy,
)


def _cmd_setup(args: argparse.Namespace) -> int:
    r = hesapla_ilk_portfoy(args.total, zpx30_fiyat=args.price, hedef_borsa_oran=args.ratio)
    print(f"ZPX30 price        : {r['zpx30_fiyat']:,.2f} TL")
    print(f"ZPX30 lots (floor) : {r['zpx30_lot']:,}")
    print(f"ZPX30 value        : {r['zpx30_gercek_tl']:,.2f} TL")
    print(f"Cash (deposit)     : {r['artik_nakit_tl']:,.2f} TL")
    print(f"Realised equity %  : {r['gercek_borsa_oran'] * 100:.2f}%  (target {args.ratio * 100:.1f}%)")
    print("\nAction: buy the lot count above; place the cash in a TL deposit. No trade is executed here.")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    lot, price, cash = args.lot, args.price, args.cash
    if lot is None or cash is None:
        from ballast.portfolio.state import load_state

        try:
            st = load_state()
        except FileNotFoundError:
            print("ERROR: portfoy_state.json not found. Provide --lot/--price/--cash, "
                  "or create state from portfoy_state.example.json.", file=sys.stderr)
            return 2
        lot = st["zpx30_lot"] if lot is None else lot
        cash = st["nakit_tl"] if cash is None else cash
    if price is None:
        from ballast.data.fetcher import fetch_macro_symbol

        price = fetch_macro_symbol(ZPX30_SYMBOL)
        if price is None:
            print(f"ERROR: could not fetch live {ZPX30_SYMBOL} price - pass --price.",
                  file=sys.stderr)
            return 2

    r = rebalance_kontrol(lot, price, cash, hedef_oran=args.ratio, bant=args.band)
    print(f"Equity ratio   : {r['mevcut_borsa_oran'] * 100:.2f}%  "
          f"(target {args.ratio * 100:.1f}% ± {args.band * 100:.1f}%)")
    print(f"Deviation      : {r['sapma'] * 100:+.2f} pp")
    if not r["rebalance_gerekli"]:
        print("Signal         : HOLD - inside band, do nothing.")
        return 0
    print(f"Signal         : {r['yon']}  {r['islem_lot']:,} lots  (~{r['islem_tl']:,.2f} TL)")
    print("\nAction: execute the direction/lots above manually. No trade is executed here.")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from ballast.portfolio.rapor_uret import uret_rapor

    print(uret_rapor(yaz=not args.no_write))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ballast.portfolio",
        description="BIST systematic portfolio maintenance - computes actions, never trades.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="compute initial lot/cash split")
    s.add_argument("--total", type=float, required=True, help="total TL to invest")
    s.add_argument("--price", type=float, default=None, help="ZPX30 price (default: live)")
    s.add_argument("--ratio", type=float, default=HEDEF_BORSA_ORAN, help="target equity ratio")
    s.set_defaults(func=_cmd_setup)

    c = sub.add_parser("check", help="band-rebalance signal")
    c.add_argument("--lot", type=int, default=None, help="ZPX30 lots held (default: state)")
    c.add_argument("--price", type=float, default=None, help="ZPX30 price (default: live)")
    c.add_argument("--cash", type=float, default=None, help="TL cash held (default: state)")
    c.add_argument("--ratio", type=float, default=HEDEF_ORAN, help="target equity ratio")
    c.add_argument("--band", type=float, default=BANT, help="band half-width")
    c.set_defaults(func=_cmd_check)

    r = sub.add_parser("report", help="generate periodic report")
    r.add_argument("--no-write", action="store_true", help="print only, do not write file")
    r.set_defaults(func=_cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
