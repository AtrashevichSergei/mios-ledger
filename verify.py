#!/usr/bin/env python3
"""Проверка журналов MIOS против якорей этого репозитория.

Журналов два: cascade — агент каскада на демо-счёте BingX, avwap — бумажный форвард якорного VWAP 4h.
Якорь без поля "ledger" — якорь каскада (так писались первые).

  python3 verify.py                      # скачать оба живых журнала и сверить со всеми якорями
  python3 verify.py ledger.jsonl         # сверить сохранённую копию журнала каскада
  python3 verify.py avwap.jsonl avwap    # сохранённую копию другого журнала
  python3 verify.py --anchor             # то же + дописать новые якоря (так делает CI)

Цепочка: h_0 = "", h_i = sha256(h_{i-1} + строка_i), строка — байты без перевода строки.
Якорь (len, tip) записан в git этого репозитория с меткой времени GitHub. Если в журнале
изменили, удалили или вставили любую строку до len, вершина на этой длине не совпадёт.
Только стандартная библиотека Python.
"""
import datetime as dt
import hashlib
import json
import pathlib
import sys
import urllib.request

URLS = {"cascade": "https://cascade-agent.fly.dev/public/ledger.jsonl",
        "avwap": "https://cascade-agent.fly.dev/public/avwap.jsonl"}
ANCHORS = pathlib.Path(__file__).resolve().parent / "anchors.jsonl"


def chain(raw: bytes) -> list[str]:
    out, h = [], ""
    for ln in raw[:raw.rfind(b"\n") + 1].splitlines():
        h = hashlib.sha256(h.encode() + ln).hexdigest()
        out.append(h)
    return out


def check(name: str, raw: bytes, anchors: list, anchor: bool) -> int:
    hs = chain(raw)
    mine = [a for a in anchors if a.get("ledger", "cascade") == name]
    bad = [a for a in mine if a["len"] > len(hs) or (a["len"] and hs[a["len"] - 1] != a["tip"])]
    for a in bad:
        print(f"РАСХОЖДЕНИЕ {name}: якорь {a['ts']} len={a['len']} tip={a['tip'][:16]}… — журнал на этой длине "
              + (f"даёт {hs[a['len'] - 1][:16]}…" if a["len"] <= len(hs) else f"короче ({len(hs)} строк)"))
    print(f"{name}: строк {len(hs)}, вершина {hs[-1] if hs else '—'}, якорей {len(mine)}, расхождений {len(bad)}")
    if bad:
        return 1
    if anchor and hs and (not mine or mine[-1]["len"] != len(hs)):
        rec = {"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "len": len(hs), "tip": hs[-1]}
        if name != "cascade":
            rec["ledger"] = name
        with ANCHORS.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print("якорь", rec)
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    anchors = [json.loads(x) for x in ANCHORS.read_text().splitlines() if x.strip()] if ANCHORS.exists() else []
    if args:
        return check(args[1] if len(args) > 1 else "cascade", pathlib.Path(args[0]).read_bytes(), anchors, "--anchor" in sys.argv)
    rc = 0
    for name, url in URLS.items():
        with urllib.request.urlopen(url, timeout=30) as r:
            rc |= check(name, r.read(), anchors, "--anchor" in sys.argv)
    return rc


if __name__ == "__main__":
    sys.exit(main())
