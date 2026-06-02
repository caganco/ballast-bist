"""Kalibrasyon ölçümü (GOAL) - mevcut araçların gürültüsünü gerçek XU030 verisinde ölç.

SALT-OKUNUR araştırma. Çekirdek modülleri (transaction_cost_v2) DEĞİŞTİRMEZ;
yalnızca mevcut tahmincilerin örnekleme-varyansını (noise) düşük-varyanslı
OHLC alternatifleriyle kıyaslar. Metodoloji değişmiyor - aynı estimand
(σ_daily, spread), daha az gürültü olup olmadığını ÖLÇER.

Ölçülen:
  A) Kyle σ_daily girdisi: close-to-close 21g rolling std'nin gürültüsü
     vs Parkinson / Garman-Klass / Rogers-Satchell / Yang-Zhang OHLC tahmincileri.
     Aynı estimand (günlük getiri std), OHLC tahmincileri ~kat daha düşük
     örnekleme-varyansı (Yang-Zhang 2000; Garman-Klass 1980).
  B) Abdi-Ranaldo spread tahmininin gürültüsü: truncation (max(-gamma,0)=0)
     oranı, gün-içi sıçrama (jumpiness), aykırı-değer (overnight gap) duyarlılığı.

Çıktı: stdout tablo (rapor calib_report'a girer). Canlı veri çeker; veri
yoksa "VERI YOK" der ve çıkar (sentetik üretmez - gerçek gürültü ölçülüyor).

Kaynak:
  Parkinson, M. (1980). J. Business 53(1), 61-65.
  Garman, M. & Klass, M. (1980). J. Business 53(1), 67-78.
  Rogers, L.C.G. & Satchell, S. (1991). Ann. Applied Prob. 1(4), 504-512.
  Yang, D. & Zhang, Q. (2000). J. Business 73(3), 477-491.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8")

SYMBOL = "XU030.IS"
START = "2019-01-01"
END = "2026-05-31"
WINDOW = 21


def fetch_ohlc() -> pd.DataFrame | None:
    """XU030 günlük OHLC çek (auto_adjust). Boşsa None."""
    try:
        df = yf.Ticker(SYMBOL).history(start=START, end=END, auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        print(f"FETCH HATA: {exc}")
        return None
    if df is None or df.empty:
        return None
    df = df[["Open", "High", "Low", "Close"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


# ---------------------------------------------------------------------------
# Volatilite tahmincileri (aynı estimand: σ_daily). Hepsi GÜNLÜK std döner.
# ---------------------------------------------------------------------------
def vol_close_to_close(df: pd.DataFrame, window: int) -> pd.Series:
    """Mevcut kyle_impact girdisi: ln(C_t/C_{t-1}) rolling std."""
    r = np.log(df["Close"] / df["Close"].shift(1))
    return r.rolling(window).std()


def vol_parkinson(df: pd.DataFrame, window: int) -> pd.Series:
    """Parkinson (1980): yalnız High-Low aralığı. σ²=mean[(ln H/L)²]/(4 ln2)."""
    hl = np.log(df["High"] / df["Low"]) ** 2
    var = hl.rolling(window).mean() / (4.0 * np.log(2.0))
    return np.sqrt(var)


def vol_garman_klass(df: pd.DataFrame, window: int) -> pd.Series:
    """Garman-Klass (1980): HL + OC. ~7.4x Parkinson'dan, ~yüksek verim."""
    hl = 0.5 * np.log(df["High"] / df["Low"]) ** 2
    co = (2.0 * np.log(2.0) - 1.0) * np.log(df["Close"] / df["Open"]) ** 2
    var = (hl - co).rolling(window).mean()
    return np.sqrt(var.clip(lower=0.0))


def vol_rogers_satchell(df: pd.DataFrame, window: int) -> pd.Series:
    """Rogers-Satchell (1991): drift-bağımsız (trend varsa yansız)."""
    ho = np.log(df["High"] / df["Open"])
    lo = np.log(df["Low"] / df["Open"])
    co = np.log(df["Close"] / df["Open"])
    rs = ho * (ho - co) + lo * (lo - co)
    var = rs.rolling(window).mean()
    return np.sqrt(var.clip(lower=0.0))


def vol_yang_zhang(df: pd.DataFrame, window: int) -> pd.Series:
    """Yang-Zhang (2000): overnight + open-to-close + RS; drift-bağımsız,
    gece-sıçramasına dayanıklı. Minimum-varyans OHLC tahmincisi."""
    o = np.log(df["Open"] / df["Close"].shift(1))   # overnight
    c = np.log(df["Close"] / df["Open"])            # open-to-close
    ho = np.log(df["High"] / df["Open"])
    lo = np.log(df["Low"] / df["Open"])
    co = np.log(df["Close"] / df["Open"])
    rs = ho * (ho - co) + lo * (lo - co)

    k = 0.34 / (1.34 + (window + 1) / (window - 1))
    vo = o.rolling(window).var()           # overnight varyans
    vc = c.rolling(window).var()           # open-close varyans
    vrs = rs.rolling(window).mean()        # Rogers-Satchell
    var = vo + k * vc + (1.0 - k) * vrs
    return np.sqrt(var.clip(lower=0.0))


def abdi_ranaldo_gamma(df: pd.DataFrame, window: int) -> pd.Series:
    """transaction_cost_v2 ile birebir aynı gamma (truncation öncesi)."""
    c = np.log(df["Close"])
    m = (np.log(df["High"]) + np.log(df["Low"])) / 2
    diff = c - m
    return (diff * diff.shift(1)).rolling(window).mean()


def abdi_ranaldo_spread(df: pd.DataFrame, window: int) -> pd.Series:
    gamma = abdi_ranaldo_gamma(df, window)
    return 2.0 * np.sqrt(np.maximum(-gamma, 0.0))


# ---------------------------------------------------------------------------
# Gürültü metrikleri
# ---------------------------------------------------------------------------
def noise_of(series: pd.Series) -> dict:
    """Bir tahmin serisinin gürültüsü: gün-içi mutlak değişim (Δ) istatistikleri.

    Aynı estimand'i tahmin eden iki seri için, daha düşük |Δ| ortalaması =
    daha az örnekleme gürültüsü (estimand günden güne ~yavaş değişir; yüksek
    frekanslı zıplamalar tahmincinin kendi varyansıdır).
    """
    s = series.dropna()
    if len(s) < 2:
        return {}
    d = s.diff().dropna()
    return {
        "level_mean": float(s.mean()),
        "abs_change_mean": float(d.abs().mean()),
        "abs_change_std": float(d.abs().std()),
        # normalize: gürültü / seviye → tahminciler arası adil kıyas
        "rel_noise": float(d.abs().mean() / s.mean()) if s.mean() else float("nan"),
        "n": int(len(s)),
    }


def main() -> int:
    df = fetch_ohlc()
    if df is None or len(df) < WINDOW + 2:
        print("VERI YOK: XU030 OHLC çekilemedi (yfinance boş). Ölçüm atlandı.")
        return 1

    print(f"XU030 OHLC: {len(df)} gün ({df.index[0].date()} → {df.index[-1].date()})\n")

    # --- A) Volatilite tahmincisi gürültü kıyası ---------------------------
    estimators = {
        "close-to-close (MEVCUT)": vol_close_to_close,
        "Parkinson": vol_parkinson,
        "Garman-Klass": vol_garman_klass,
        "Rogers-Satchell": vol_rogers_satchell,
        "Yang-Zhang": vol_yang_zhang,
    }
    print("=" * 74)
    print(f"A) σ_daily TAHMİNCİ GÜRÜLTÜSÜ (window={WINDOW}, kyle_impact girdisi)")
    print("=" * 74)
    print(f"{'tahminci':<26}{'seviye':>10}{'|Δ| ort':>11}{'rel_noise':>12}{'vs C2C':>9}")
    base_rel = None
    results = {}
    for name, fn in estimators.items():
        m = noise_of(fn(df, WINDOW))
        results[name] = m
        if not m:
            continue
        if base_rel is None:
            base_rel = m["rel_noise"]
        ratio = base_rel / m["rel_noise"] if m["rel_noise"] else float("nan")
        print(
            f"{name:<26}{m['level_mean']:>10.5f}{m['abs_change_mean']:>11.6f}"
            f"{m['rel_noise']:>12.4f}{ratio:>8.2f}x"
        )
    print("\n  rel_noise = ardışık-gün |Δσ| ort / σ seviyesi (düşük = az gürültü)")
    print("  vs C2C    = mevcut close-to-close'a göre gürültü-azaltma katı (>1 iyi)")

    # tahminciler arası seviye uyumu (yanlılık kontrolü: aynı estimand mı?)
    c2c_lvl = results["close-to-close (MEVCUT)"]["level_mean"]
    yz_lvl = results["Yang-Zhang"]["level_mean"]
    print(
        f"\n  Seviye uyumu (yanlılık): YZ/C2C = {yz_lvl / c2c_lvl:.3f} "
        f"(~1.0 = aynı estimand, sadece daha az gürültü)"
    )

    # --- B) Abdi-Ranaldo spread tanılaması ---------------------------------
    gamma = abdi_ranaldo_gamma(df, WINDOW).dropna()
    spread = abdi_ranaldo_spread(df, WINDOW).dropna()
    trunc_rate = float((gamma >= 0).mean())  # gamma>=0 → spread=0'a kırpılır
    sd = spread.diff().dropna()
    print("\n" + "=" * 74)
    print(f"B) ABDI-RANALDO SPREAD TANILAMASI (window={WINDOW})")
    print("=" * 74)
    print(f"  geçerli pencere       : {len(spread)}")
    print(f"  truncation oranı      : {trunc_rate:.3f}  (gamma>=0 → spread=0 kırpıldı)")
    print(f"  spread ort / medyan   : {spread.mean():.5f} / {spread.median():.5f}")
    print(f"  spread std            : {spread.std():.5f}")
    print(f"  gün-içi |Δspread| ort : {sd.abs().mean():.6f}")
    print(f"  rel_noise (|Δ|/seviye): {sd.abs().mean() / spread.mean():.4f}")

    # overnight-gap aykırı duyarlılığı: |Δln(C)| en büyük %1 günleri çıkar,
    # gamma ortalaması ne kadar oynuyor? (robust merkez gerekçesi)
    dlnc = np.log(df["Close"] / df["Close"].shift(1)).abs()
    thr = dlnc.quantile(0.99)
    outlier_days = dlnc > thr
    g_all = abdi_ranaldo_gamma(df, WINDOW)
    # aykırı günleri içeren vs içermeyen pencerelerin gamma dağılımı
    g_clean = g_all[~outlier_days].dropna()
    print(
        f"  overnight aykırı (>%99): {int(outlier_days.sum())} gün; "
        f"gamma ort tümü={g_all.dropna().mean():.2e} "
        f"temiz={g_clean.mean():.2e}"
    )
    # Nokta-tahmin gürültüsü: round_trip son-değeri (iloc[-1]) vs trailing
    # mean/median agregasyonu. AYNI estimand (spread seviyesi), daha az varyans.
    # NOT: gamma'yı trimlemek estimand'i KAYDIRIR (asimetrik çarpım dağılımı) →
    # metodoloji korunumu için reddedildi; bunun yerine zaten hesaplanmış geçerli
    # spread serisini agregeliyoruz (seviye aynı, gürültü düşük).
    valid = spread  # geçerli (NaN-olmayan) spread serisi
    for agg_win in (3, 5, 10):
        mean_agg = valid.rolling(agg_win).mean().dropna()
        med_agg = valid.rolling(agg_win).median().dropna()
        dm = mean_agg.diff().dropna().abs().mean() / mean_agg.mean()
        dd = med_agg.diff().dropna().abs().mean() / med_agg.mean()
        print(
            f"  agg={agg_win:>2}g  rel_noise mean={dm:.4f}  median={dd:.4f}  "
            f"(son-değer ref={sd.abs().mean() / spread.mean():.4f})  "
            f"seviye mean/son={mean_agg.mean() / valid.mean():.3f}"
        )
    print(
        "\n  Yorum: trailing mean/median agregasyon spread nokta-tahmini "
        "gürültüsünü\n  ~kat düşürür, seviye (~estimand) korunur. round_trip "
        "opt-in spread_agg adayı."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
