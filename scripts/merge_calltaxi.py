"""API 정제본(calltaxi_2025_정제.csv)을 기준으로 보유 탑승내역 CSV를 병합.

매칭 키: (분단위 예정일시/receipttime, 출발구/동, 목적구/동)
- API에 없는 보유CSV 컬럼(접수일시·하차일시·이용목적·요금·승차거리·차량구분·장애유형)을 추가.
- 매칭 안 된 API 행: 추가 컬럼 공란 + 매칭여부=N
- 매칭 안 된 보유CSV 행(취소 건 등): calltaxi_2025_보유CSV_미매칭.csv 로 분리
"""
import csv
import os
from collections import defaultdict, deque

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_CSV = os.path.join(BASE_DIR, "데이터", "api", "calltaxi_2025_정제.csv")
EXIST_CSV = os.path.join(BASE_DIR, "데이터", "서울시설공단_장애인콜택시 탑승내역_20251231.csv")
MERGED_CSV = os.path.join(BASE_DIR, "데이터", "api", "calltaxi_2025_병합.csv")
UNMATCHED_EXIST_CSV = os.path.join(BASE_DIR, "데이터", "api", "calltaxi_2025_보유CSV_미매칭.csv")
REPORT_PATH = os.path.join(BASE_DIR, "데이터", "api", "merge_리포트.md")

EXTRA_COLS = ["접수일시", "하차일시", "이용목적", "요금", "승차거리", "차량구분_보유", "장애유형"]


def minute_key(ts):
    return ts[:16] if ts else ""


def main():
    print("보유 CSV 로드 및 일자별 인덱싱 중...")
    with open(EXIST_CSV, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        exist_header = next(reader)
        idx = {name: i for i, name in enumerate(exist_header)}
        # day -> key -> deque of row(list)
        buckets = defaultdict(lambda: defaultdict(deque))
        all_rows_by_day = defaultdict(list)
        n_exist = 0
        for row in reader:
            sched = row[idx["예정일시"]]
            if not sched:
                continue
            day = sched[:10].replace("-", "")
            key = (
                minute_key(sched),
                row[idx["출발구"]], row[idx["출발동"]],
                row[idx["목적구"]], row[idx["목적동"]],
            )
            buckets[day][key].append(row)
            all_rows_by_day[day].append(row)
            n_exist += 1
    print(f"  보유CSV {n_exist:,}행 인덱싱 완료")

    print("API 정제본 스트리밍 매칭 중...")
    n_api = 0
    n_matched = 0
    with open(API_CSV, encoding="utf-8-sig") as f_api, \
         open(MERGED_CSV, "w", newline="", encoding="utf-8-sig") as f_out:
        api_reader = csv.DictReader(f_api)
        out_fields = api_reader.fieldnames + EXTRA_COLS + ["매칭여부"]
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        writer.writeheader()

        for row in api_reader:
            n_api += 1
            day = row["date"]
            key = (
                minute_key(row["receipttime"]),
                row["startpos1"], row["startpos2"],
                row["endpos1"], row["endpos2"],
            )
            dq = buckets.get(day, {}).get(key)
            out = dict(row)
            if dq:
                erow = dq.popleft()
                out["접수일시"] = erow[idx["접수일시"]]
                out["하차일시"] = erow[idx["하차일시"]]
                out["이용목적"] = erow[idx["이용목적"]]
                out["요금"] = erow[idx["요금"]]
                out["승차거리"] = erow[idx["승차거리"]]
                out["차량구분_보유"] = erow[idx["차량구분"]]
                out["장애유형"] = erow[idx["장애유형"]]
                out["매칭여부"] = "Y"
                n_matched += 1
            else:
                for c in EXTRA_COLS:
                    out[c] = ""
                out["매칭여부"] = "N"
            writer.writerow(out)
            if n_api % 200000 == 0:
                print(f"  진행 {n_api:,}행...")

    print("매칭 안 된 보유CSV 행 분리 중...")
    n_unmatched_exist = 0
    with open(UNMATCHED_EXIST_CSV, "w", newline="", encoding="utf-8-sig") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(exist_header)
        for day, rows in all_rows_by_day.items():
            key_remaining = buckets[day]
            # dq에 남아있는 행들만 미매칭
            for key, dq in key_remaining.items():
                for row in dq:
                    writer.writerow(row)
                    n_unmatched_exist += 1

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 병합 리포트\n\n")
        f.write(f"- API 정제본 행 수: {n_api:,}\n")
        f.write(f"- 매칭 성공: {n_matched:,} ({n_matched/n_api*100:.1f}%)\n")
        f.write(f"- API 중 미매칭: {n_api-n_matched:,} ({(n_api-n_matched)/n_api*100:.1f}%)\n")
        f.write(f"- 보유CSV 전체: {n_exist:,}\n")
        f.write(f"- 보유CSV 중 미매칭(취소 건 등, 별도 분리): {n_unmatched_exist:,} ({n_unmatched_exist/n_exist*100:.1f}%)\n\n")
        f.write(f"산출물:\n- `calltaxi_2025_병합.csv` — API 기준 + 보유CSV 추가컬럼({', '.join(EXTRA_COLS)})\n")
        f.write(f"- `calltaxi_2025_보유CSV_미매칭.csv` — 보유CSV에만 있는 잔여 행(취소 건 등)\n")

    print(f"완료. 매칭 {n_matched:,}/{n_api:,} ({n_matched/n_api*100:.1f}%), 보유CSV 미매칭 {n_unmatched_exist:,}행")
    print(f"리포트: {REPORT_PATH}")


if __name__ == "__main__":
    main()
