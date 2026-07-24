"""API 수집본(calltaxi_2025_정제.csv) vs 보유 탑승내역 CSV 표본 대조."""
import csv
import os
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_CSV = os.path.join(BASE_DIR, "데이터", "api", "csv", "calltaxi_2025_정제.csv")
EXIST_CSV = os.path.join(BASE_DIR, "데이터", "서울시설공단_장애인콜택시 탑승내역_20251231.csv")
REPORT_PATH = os.path.join(BASE_DIR, "데이터", "api", "cross_validate_리포트.md")

SAMPLE_DAYS = ["20250101", "20250615", "20250930", "20251231"]


def day_counts_existing():
    counts = Counter()
    min_d = max_d = None
    with open(EXIST_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("접수일시", "")
            if not ts:
                continue
            d = ts[:10].replace("-", "")
            counts[d] += 1
            if min_d is None or d < min_d:
                min_d = d
            if max_d is None or d > max_d:
                max_d = d
    return counts, min_d, max_d


def day_counts_api():
    counts = Counter()
    with open(API_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row["date"]] += 1
    return counts


def minute_key(ts):
    return ts[:16] if ts else ""


def sample_match(day):
    api_rows = []
    with open(API_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] == day:
                api_rows.append(row)

    exist_rows = []
    y, m, d = day[:4], day[4:6], day[6:8]
    prefix = f"{y}-{m}-{d}"
    with open(EXIST_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("접수일시", "").startswith(prefix):
                exist_rows.append(row)

    api_keys = Counter(
        (minute_key(r["receipttime"]), r["startpos1"], r["startpos2"], r["endpos1"], r["endpos2"])
        for r in api_rows
    )
    exist_keys_receipt = Counter(
        (minute_key(r["접수일시"]), r["출발구"], r["출발동"], r["목적구"], r["목적동"])
        for r in exist_rows
    )
    exist_keys_sched = Counter(
        (minute_key(r["예정일시"]), r["출발구"], r["출발동"], r["목적구"], r["목적동"])
        for r in exist_rows
    )

    matched_receipt = sum((api_keys & exist_keys_receipt).values())
    matched_sched = sum((api_keys & exist_keys_sched).values())
    return len(api_rows), len(exist_rows), matched_receipt, matched_sched


def main():
    print("보유 CSV 일자별 집계 중 (172만행)...")
    exist_counts, min_d, max_d = day_counts_existing()
    print("API 정제본 일자별 집계 중...")
    api_counts = day_counts_api()

    lines = ["# API 수집본 vs 보유 탑승내역 CSV 대조 리포트\n"]
    lines.append(f"- 보유 CSV 커버 기간: {min_d} ~ {max_d}\n")
    lines.append(f"- 보유 CSV 전체 행 수: {sum(exist_counts.values()):,}\n")
    lines.append(f"- API 정제본 전체 행 수: {sum(api_counts.values()):,}\n\n")

    lines.append("## 표본 일자 대조 (분단위 시각 + 출발/도착 구·동 키 매칭)\n\n")
    lines.append("API의 receipttime을 보유CSV의 접수일시/예정일시 각각과 대조 (어느 쪽 대응인지 확인 목적)\n\n")
    lines.append("| 일자 | API 행수 | 보유CSV 행수 | 매칭(접수일시 기준) | 매칭(예정일시 기준) |\n|---|---:|---:|---:|---:|\n")
    for day in SAMPLE_DAYS:
        a, e, m_r, m_s = sample_match(day)
        rate_r = m_r / a * 100 if a else 0
        rate_s = m_s / a * 100 if a else 0
        lines.append(f"| {day} | {a:,} | {e:,} | {m_r:,} ({rate_r:.1f}%) | {m_s:,} ({rate_s:.1f}%) |\n")

    lines.append("\n## 연간 일자별 건수 차이 (|API - 보유| 상위 10일)\n\n")
    all_days = set(api_counts) | set(exist_counts)
    diffs = sorted(
        ((d, api_counts.get(d, 0), exist_counts.get(d, 0), abs(api_counts.get(d, 0) - exist_counts.get(d, 0)))
         for d in all_days),
        key=lambda x: -x[3],
    )[:10]
    lines.append("| 일자 | API | 보유CSV | 차이 |\n|---|---:|---:|---:|\n")
    for d, a, e, diff in diffs:
        lines.append(f"| {d} | {a:,} | {e:,} | {diff:,} |\n")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("완료:", REPORT_PATH)


if __name__ == "__main__":
    main()
