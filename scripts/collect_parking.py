"""공영주차장(GetParkInfo)·시영주차장(GetParkingInfo) 목록 수집 및 PKLT_CD 대조."""
import csv
import json
import os
import re
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
OUT_DIR = os.path.join(BASE_DIR, "데이터", "api")
CSV_DIR = os.path.join(OUT_DIR, "csv")
os.makedirs(CSV_DIR, exist_ok=True)


def load_api_key():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("API_KEY"):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("API_KEY not found in .env")


def fetch_json(key, service, start, end):
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect_all(key, service, page_size=1000):
    rows = []
    start = 1
    total = None
    while total is None or start <= total:
        end = start + page_size - 1
        data = fetch_json(key, service, start, end)
        body = data.get(service)
        if body is None:
            raise RuntimeError(f"{service} error: {data}")
        code = body["RESULT"]["CODE"]
        if code != "INFO-000":
            raise RuntimeError(f"{service} {start}-{end}: {body['RESULT']}")
        total = body["list_total_count"]
        rows.extend(body.get("row", []))
        start = end + 1
        time.sleep(1.0)
    return rows


def write_csv(path, rows):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def normalize(name):
    return re.sub(r"\s+", "", name or "")


def main():
    key = load_api_key()

    print("공영주차장(GetParkInfo) 수집 중...")
    gy = collect_all(key, "GetParkInfo")
    print(f"  {len(gy)}행 수집 완료")

    print("시영주차장(GetParkingInfo) 수집 중...")
    si = collect_all(key, "GetParkingInfo")
    print(f"  {len(si)}행 수집 완료")

    si_codes = {r["PKLT_CD"] for r in si}
    for r in gy:
        r["시영여부"] = "Y" if r["PKLT_CD"] in si_codes else "N"

    write_csv(os.path.join(CSV_DIR, "공영주차장_목록.csv"), gy)
    write_csv(os.path.join(CSV_DIR, "시영주차장_목록.csv"), si)

    gy_by_code = {r["PKLT_CD"]: r for r in gy}
    gy_names_norm = {normalize(r["PKLT_NM"]): r for r in gy}

    matched, code_mismatch = [], []
    for r in si:
        code = r["PKLT_CD"]
        if code in gy_by_code:
            matched.append((r, gy_by_code[code], "PKLT_CD 일치"))
        else:
            alt = gy_names_norm.get(normalize(r["PKLT_NM"]))
            if alt:
                matched.append((r, alt, "명칭 일치(PKLT_CD 불일치)"))
            else:
                code_mismatch.append(r)

    report_path = os.path.join(OUT_DIR, "시영공영_대조_리포트.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 시영↔공영주차장 목록 대조 리포트\n\n")
        f.write(f"- 시영(GetParkingInfo) 전체: {len(si)}건\n")
        f.write(f"- 공영(GetParkInfo) 전체: {len(gy)}건\n")
        f.write(f"- 매칭: {len(matched)}건\n")
        f.write(f"- 불일치(공영 목록에서 못 찾음): {len(code_mismatch)}건\n\n")
        f.write("## 불일치 목록\n\n")
        f.write("| PKLT_CD | PKLT_NM | ADDR |\n|---|---|---|\n")
        for r in code_mismatch:
            f.write(f"| {r['PKLT_CD']} | {r['PKLT_NM']} | {r.get('ADDR','')} |\n")

    좌표결측 = sum(1 for r in gy if not r.get("LAT") or not r.get("LOT") or r.get("LAT") == "0")
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(f"\n## 공영주차장 좌표 결측\n\n- LAT/LOT 결측 또는 0: {좌표결측}건 / {len(gy)}건\n")

    print(f"매칭 {len(matched)}건 / 불일치 {len(code_mismatch)}건 -> {report_path}")
    print("완료.")


if __name__ == "__main__":
    main()
