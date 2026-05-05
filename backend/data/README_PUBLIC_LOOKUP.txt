File public_lookup.xlsx tidak perlu dibuat manual.

Mulai patch ini, data pencarian publik NIM dibuat otomatis ketika admin klik Generate Excel Final.

Sumber data:
- File Rekapitulasi Nilai yang diupload admin
- Baris yang berhasil masuk ke sheet kelas final
- Kolom yang dipakai: NIM, NAMA, KODE KELAS PAI

Jika deploy ke hosting dengan storage ephemeral, set PUBLIC_LOOKUP_FILE ke path persistent disk, contoh:
PUBLIC_LOOKUP_FILE=/data/public_lookup.xlsx

Kalau file rekap tidak punya kolom NIM, generate Excel tetap jalan, tetapi pencarian publik NIM tidak bisa dibuat.
