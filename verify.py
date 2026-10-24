#!/usr/bin/env python3
"""Проверка журнала агента каскада MIOS против якорей этого репозитория.

  python3 verify.py                      # скачать живой журнал и сверить со всеми якорями
  python3 verify.py ledger.jsonl         # сверить сохранённую копию
  python3 verify.py --anchor             # то же + дописать новый якорь (так делает CI)

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

URL = "https://cascade-agent.fly.dev/public/ledger.jsonl"
ANCHORS = pathlib.Path(__file__).resolve().parent / "anchors.jsonl"


def chain(raw: bytes) -> list[str]:
    out, h = [], ""
    for ln in raw[:raw.rfind(b"\n") + 1].splitlines():
        h = hashlib.sha256(h.encode() + ln).hexdigest()
        out.append(h)
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        raw = pathlib.Path(args[0]).read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=30) as r:
            raw = r.read()
    hs = chain(raw)
    anchors = [json.loads(x) for x in ANCHORS.read_text().splitlines() if x.strip()] if ANCHORS.exists() else []
    bad = [a for a in anchors if a["len"] > len(hs) or (a["len"] and hs[a["len"] - 1] != a["tip"])]
    for a in bad:
        print(f"РАСХОЖДЕНИЕ: якорь {a['ts']} len={a['len']} tip={a['tip'][:16]}… — журнал на этой длине "
              + (f"даёт {hs[a['len'] - 1][:16]}…" if a["len"] <= len(hs) else f"короче ({len(hs)} строк)"))
    print(f"строк {len(hs)}, вершина {hs[-1] if hs else '—'}, якорей {len(anchors)}, расхождений {len(bad)}")
    if bad:
        return 1
    if "--anchor" in sys.argv and hs and (not anchors or anchors[-1]["len"] != len(hs)):
        rec = {"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "len": len(hs), "tip": hs[-1]}
        with ANCHORS.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print("якорь", rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
