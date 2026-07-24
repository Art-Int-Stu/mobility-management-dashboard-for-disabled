"""장애인콜택시(disabledCalltaxi) 2025년 건별 운행기록 일별 수집."""
import csv
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
OUT_DIR = os.path.join(BASE_DIR, "데이터", "api")
CSV_DIR = os.path.join(OUT_DIR, "csv")
os.makedirs(CSV_DIR, exist_ok=True)

CSV_PATH = os.path.join(CSV_DIR, "calltaxi_2025.csv")
CHECKPOINT_PATH = os.path.join(OUT_DIR, "checkpoint.json")
FAILED_LOG_PATH = os.path.join(OUT_DIR, "collect_calltaxi_failed.log")

START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)
DELAY = 0.3
MAX_RETRY = 3
FIELDS = ["date", "no", "cartype", "receipttime", "settime", "ridetime",
          "startpos1", "startpos2", "endpos1", "endpos2"]


def load_api_key():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("API_KEY"):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("API_KEY not found in .env")


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"last_done": None}


def save_checkpoint(cp):
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False)


def fetch_day(key, day_str):
    url = f"http://openapi.seoul.go.kr:8088/{key}/xml/disabledCalltaxi/1/1000/{day_str}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    root = ET.fromstring(raw)
    result = root.find("RESULT")
    code = result.find("CODE").text if result is not None else None
    if code != "INFO-000":
        msg = result.find("MESSAGE").text if result is not None else raw[:200]
        raise RuntimeError(f"{code}: {msg}")
    total = int(root.findtext("list_total_count", "0"))
    rows = []
    for item in root.iter("item"):
        row = {tag: (item.findtext(tag) or "") for tag in
               ["no", "cartype", "receipttime", "settime", "ridetime",
                "startpos1", "startpos2", "endpos1", "endpos2"]}
        rows.append(row)
    if len(rows) != total:
        print(f"  [경고] list_total_count={total} vs 파싱된 item 수={len(rows)} (불일치)")
    return rows


def main():
    key = load_api_key()
    cp = load_checkpoint()
    last_done = cp.get("last_done")
    resume_date = (date.fromisoformat(last_done) + timedelta(days=1)) if last_done else START_DATE

    write_header = not os.path.exists(CSV_PATH)
    csv_file = open(CSV_PATH, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
    if write_header:
        writer.writeheader()

    failed_days = []
    d = resume_date
    total_rows = 0
    while d <= END_DATE:
        day_str = d.strftime("%Y%m%d")
        ok = False
        for attempt in range(1, MAX_RETRY + 1):
            try:
                rows = fetch_day(key, day_str)
                for r in rows:
                    r["date"] = day_str
                    writer.writerow(r)
                csv_file.flush()
                total_rows += len(rows)
                print(f"{day_str}: {len(rows)}건 (누적 {total_rows})")
                ok = True
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f"{day_str} 시도 {attempt}/{MAX_RETRY} 실패: {e} -> {wait}s 후 재시도")
                time.sleep(wait)
        if not ok:
            failed_days.append(day_str)
            with open(FAILED_LOG_PATH, "a", encoding="utf-8") as flog:
                flog.write(f"{day_str}\n")
        cp["last_done"] = day_str
        save_checkpoint(cp)
        d += timedelta(days=1)
        time.sleep(DELAY)

    csv_file.close()
    print(f"\n완료. 총 {total_rows}행 수집. 실패 일자: {len(failed_days)}건")
    if failed_days:
        print("실패 목록:", failed_days)


if __name__ == "__main__":
    main()
