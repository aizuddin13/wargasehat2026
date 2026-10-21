#!/usr/bin/env python3
"""
Warga Sehat 2026 — tarik data dari Google Sheets (CSV awam) dan proses
jadi data/latest.json untuk papar di laman status (GitHub Pages).

Kaedah akses data: Sheet di-'share' sebagai "Anyone with the link - Viewer",
jadi URL export CSV standard Google Sheets boleh diakses tanpa kredential.
Tiada data sensitif (no. kad, dsb.) dalam sheet ini — hanya nama, jabatan,
tarikh dan jumlah langkah.
"""
import csv
import io
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# KONFIGURASI — tukar di sini jika perlu
# ---------------------------------------------------------------------------
SPREADSHEET_ID = "1QB7griCe7FDrvBb8tlC2NEmk7WiNoV9L4OpWJygoXy4"
SHEET_GID = "906227023"  # tab "Form Responses 1"
CSV_URL = os.environ.get(
    "SHEET_CSV_URL",
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}",
)

# Tempoh rasmi program (tarikh dalam lajur "Tarikh Langkah" ikut tempoh ni)
# NOTA: tempoh di bawah untuk PILOT TEST (21-27 Okt 2026, 16 peserta sampel).
# TUKAR BALIK kepada 1-30 Nov 2026 sebelum program rasmi bermula, dan padam
# baris data pilot dalam Google Sheets selepas pilot selesai.
PROGRAM_START = datetime(2026, 10, 21)
PROGRAM_END = datetime(2026, 10, 27)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")

# Lajur-lajur yang kita perlukan (dikenal pasti ikut NAMA header, bukan posisi,
# supaya kalau tambah/susun semula soalan dalam Form, script ni tak pecah)
COL_JABATAN = "Jabatan"
COL_TARIKH = "Tarikh Langkah"
COL_LANGKAH = "Jumlah langkah anda hari ini"
COL_NAMA = "Nama (Gabungan)"
COL_TIMESTAMP = "Timestamp"


def fetch_csv_rows(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw)))


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_steps(value: str):
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def main():
    rows = fetch_csv_rows(CSV_URL)

    dept_totals = defaultdict(int)
    dept_counts = defaultdict(int)
    dept_participants = defaultdict(set)
    individuals = []

    skipped = 0

    for row in rows:
        nama = (row.get(COL_NAMA) or "").strip()
        jabatan = (row.get(COL_JABATAN) or "").strip()
        tarikh = parse_date(row.get(COL_TARIKH))
        langkah = parse_steps(row.get(COL_LANGKAH))

        if not nama or not jabatan or tarikh is None or langkah is None:
            skipped += 1
            continue
        if not (PROGRAM_START <= tarikh <= PROGRAM_END):
            continue

        dept_totals[jabatan] += langkah
        dept_counts[jabatan] += 1
        dept_participants[jabatan].add(nama)

        individuals.append(
            {
                "nama": nama,
                "jabatan": jabatan,
                "tarikh": tarikh.strftime("%Y-%m-%d"),
                "langkah": langkah,
                "timestamp": (row.get(COL_TIMESTAMP) or "").strip(),
            }
        )

    ranking = []
    for jabatan, total in dept_totals.items():
        count = dept_counts[jabatan]
        ranking.append(
            {
                "jabatan": jabatan,
                "purata_harian": round(total / count, 1) if count else 0,
                "jumlah_rekod": count,
                "bilangan_peserta": len(dept_participants[jabatan]),
                "jumlah_langkah": total,
            }
        )
    ranking.sort(key=lambda d: d["purata_harian"], reverse=True)
    for i, d in enumerate(ranking, start=1):
        d["kedudukan"] = i

    individuals.sort(key=lambda r: (r["tarikh"], r["timestamp"]), reverse=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "program": {
            "nama": "Warga Sehat 2026",
            "mula": PROGRAM_START.strftime("%Y-%m-%d"),
            "tamat": PROGRAM_END.strftime("%Y-%m-%d"),
        },
        "ranking_jabatan": ranking,
        "rekod_individu": individuals,
        "meta": {
            "jumlah_rekod_sah": len(individuals),
            "rekod_diabaikan": skipped,
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Ditulis {OUTPUT_PATH}: {len(ranking)} jabatan, {len(individuals)} rekod sah, {skipped} diabaikan.")


if __name__ == "__main__":
    main()
