# Board Kehadiran Karyawan (Streamlit + Google Sheets)

Dashboard kehadiran karyawan, tampilannya di Streamlit tapi datanya tersimpan permanen di Google Spreadsheet.

---

## Bagian 1 — Setup Google Cloud & Spreadsheet (dilakukan sekali di awal)

### 1. Buat Google Cloud Project
1. Buka [console.cloud.google.com](https://console.cloud.google.com)
2. Klik "Select a project" → "New Project" → beri nama bebas (misal `board-kehadiran`) → Create

### 2. Aktifkan API yang dibutuhkan
1. Di search bar Google Cloud Console, cari **Google Sheets API** → klik **Enable**
2. Cari juga **Google Drive API** → klik **Enable**

### 3. Buat Service Account (akun robot untuk mengakses Sheets)
1. Menu ☰ → **IAM & Admin** → **Service Accounts** → **Create Service Account**
2. Beri nama bebas (misal `board-kehadiran-bot`) → Create and Continue → Done (role boleh dilewati/skip)
3. Klik service account yang baru dibuat → tab **Keys** → **Add Key** → **Create new key** → pilih **JSON** → Create
4. File JSON otomatis ter-download — **simpan baik-baik, ini kunci rahasia**
5. Catat juga alamat emailnya, formatnya seperti: `nama@nama-project.iam.gserviceaccount.com`

### 4. Buat Google Spreadsheet
1. Buka [sheets.google.com](https://sheets.google.com) → buat spreadsheet baru, beri nama misal "Data Kehadiran Karyawan"
2. Ambil **Spreadsheet ID** dari URL-nya:
   `https://docs.google.com/spreadsheets/d/`**`INI_SPREADSHEET_ID_NYA`**`/edit`
3. Klik tombol **Share** di spreadsheet → tempel email service account dari langkah 3.5 di atas → beri akses **Editor** → Send

   (Sheet "Employees" dan "Attendance" akan dibuat otomatis oleh aplikasi saat pertama kali dijalankan, tidak perlu dibuat manual)

---

## Bagian 2 — Coba di komputer sendiri

1. Install library:
   ```bash
   pip install -r requirements.txt
   ```
2. Salin `.streamlit/secrets_example.toml` menjadi `.streamlit/secrets.toml`
3. Buka file JSON hasil download di langkah 3.4, salin isinya ke bagian `[gcp_service_account]` di `secrets.toml` (field-nya sudah sama persis)
4. Isi `SPREADSHEET_ID` dengan ID dari langkah 4.2
5. Jalankan:
   ```bash
   streamlit run app.py
   ```

---

## Bagian 3 — Deploy supaya bisa diakses lewat link

1. Upload semua file **kecuali** `.streamlit/secrets.toml` (sudah otomatis diabaikan lewat `.gitignore`) ke repository GitHub
2. Buka [share.streamlit.io](https://share.streamlit.io) → login dengan akun GitHub → **New app** → pilih repository ini → pilih `app.py` → Deploy
3. Setelah dibuat, buka menu **⋮ (titik tiga)** pada app → **Settings** → **Secrets**
4. Tempel isi `secrets.toml` yang sudah lengkap terisi (dari langkah 2 di atas) ke kolom Secrets tersebut → Save
5. App akan otomatis restart dan siap dipakai. Link-nya (`https://nama-app.streamlit.app`) bisa dibagikan ke ibu dan staf HR

---

## Kenapa cara ini lebih aman untuk data jangka panjang

- Data tidak disimpan di file lokal aplikasi (yang bisa hilang saat server restart), tapi di Google Spreadsheet milik sendiri
- Bisa dibuka & di-backup langsung dari Google Sheets kapan saja
- Kalau suatu saat aplikasi Streamlit-nya bermasalah, datanya tetap aman di spreadsheet

## Ganti foto placeholder dengan foto asli nanti

Selama foto asli belum ada, aplikasi otomatis pakai foto sementara. Kalau nanti foto aslinya sudah siap:

1. Upload foto ke Google Drive
2. Klik kanan file → **Share** → ubah jadi **Anyone with the link** bisa lihat
3. Salin link-nya, ambil bagian ID-nya (kode acak di antara `/d/` dan `/view`)
4. Bentuk URL foto yang bisa dipakai: `https://drive.google.com/uc?export=view&id=ID_FILE_TADI`
5. Buka spreadsheet "Employees", isi kolom `photo_url` di baris karyawan terkait dengan URL tadi
6. Refresh aplikasi Streamlit-nya — foto langsung berubah

## Kalau ada yang mau dirundingin lagi
Beberapa hal yang bisa disesuaikan lebih lanjut kalau dibutuhkan:
- Tambah kolom foto karyawan
- Tambah proteksi login/password sebelum masuk dashboard
- Export otomatis ke rekap bulanan
- Notifikasi kalau ada yang belum diisi statusnya sampai jam tertentu

Tinggal bilang aja mau yang mana.
