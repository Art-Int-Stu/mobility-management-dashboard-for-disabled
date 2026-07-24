"""calltaxi_2025.csv(원본) 검증·정제 -> calltaxi_2025_정제.csv.

- 완전중복 행 제거
- receipttime/settime/ridetime을 ISO(YYYY-MM-DD HH:MM:SS)로 정규화 (파싱 불능 시 원문 보존 + 플래그)
- 검증 리포트(일자별 건수, 중복 수, 시각 정규화 실패율) 출력
"""
import csv
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "데이터", "api")
CSV_DIR = os.path.join(OUT_DIR, "csv")
RAW_CSV = os.path.join(CSV_DIR, "calltaxi_2025.csv")
CLEAN_CSV = os.path.join(CSV_DIR, "calltaxi_2025_정제.csv")
REPORT_PATH = os.path.join(OUT_DIR, "calltaxi_2025_검증_리포트.md")

TIME_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"(?:\s+(?P<ap>오전|오후)\s+(?P<h>\d{1,2}):(?P<mi>\d{2}):(?P<s>\d{2}))?$"
)


def normalize_time(raw):
    """'2025-04-01 오전 12:03:00' -> '2025-04-01 00:03:00'. 시각 없으면 (date_only, True)."""
    if not raw:
        return "", True
    m = TIME_RE.match(raw.strip())
    if not m:
        return raw, True  # 파싱 불능: 원문 보존 + 실패 플래그
    y, mo, d = m.group("y"), m.group("m"), m.group("d")
    if m.group("ap") is None:
        return f"{y}-{mo}-{d}", True  # 날짜만 있음
    h = int(m.group("h"))
    ap = m.group("ap")
    if ap == "오후" and h != 12:
        h += 12
    if ap == "오전" and h == 12:
        h = 0
    return f"{y}-{mo}-{d} {h:02d}:{m.group('mi')}:{m.group('s')}", False


def main():
    with open(RAW_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total_raw = len(rows)

    seen = set()
    deduped = []
    dup_count = 0
    for r in rows:
        key = tuple(r.values())
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)
        deduped.append(r)

    fail_counts = {"receipttime": 0, "settime": 0, "ridetime": 0}
    day_counts = {}
    for r in deduped:
        for field in ("receipttime", "settime", "ridetime"):
            norm, failed = normalize_time(r.get(field, ""))
            r[field] = norm
            if failed:
                fail_counts[field] += 1
        day_counts[r["date"]] = day_counts.get(r["date"], 0) + 1

    with open(CLEAN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(deduped)

    total_clean = len(deduped)
    days_covered = len(day_counts)
    min_day = min(day_counts) if day_counts else None
    max_day = max(day_counts) if day_counts else None

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# calltaxi_2025 검증 리포트\n\n")
        f.write(f"- 원본 행 수: {total_raw:,}\n")
        f.write(f"- 완전중복 제거: {dup_count:,}건\n")
        f.write(f"- 정제본 행 수: {total_clean:,}\n")
        f.write(f"- 수집 일자 수: {days_covered} / 365\n")
        f.write(f"- 커버 기간: {min_day} ~ {max_day}\n\n")
        f.write("## 시각 필드 정규화 실패(날짜만 있거나 파싱 불능)\n\n")
        f.write("| 필드 | 실패 건수 | 비율 |\n|---|---:|---:|\n")
        for field, cnt in fail_counts.items():
            f.write(f"| {field} | {cnt:,} | {cnt/total_clean*100:.2f}% |\n")
        f.write("\n## 일자별 건수 (처음 5 / 마지막 5)\n\n")
        sorted_days = sorted(day_counts.items())
        f.write("| 일자 | 건수 |\n|---|---:|\n")
        for d, c in sorted_days[:5]:
            f.write(f"| {d} | {c:,} |\n")
        f.write("| ... | ... |\n")
        for d, c in sorted_days[-5:]:
            f.write(f"| {d} | {c:,} |\n")

    print(f"원본 {total_raw:,} -> 중복제거 {dup_count:,} -> 정제본 {total_clean:,}")
    print(f"시각 정규화 실패: {fail_counts}")
    print(f"리포트: {REPORT_PATH}")
    print(f"정제 CSV: {CLEAN_CSV}")


if __name__ == "__main__":
    main()
