# Pharos Mainnet Sender

Script Python untuk mengirim **seluruh saldo (sweep)** dari banyak wallet ke satu alamat tujuan di jaringan Pharos, secara paralel (multi-thread) dengan mekanisme retry otomatis saat kena rate limit (HTTP 429).

## ✨ Fitur

- Mendukung wallet dalam bentuk **private key** maupun **seed phrase** (12/15/18/21/24 kata)
- Bisa memuat wallet dari dua file sekaligus (`wallet.txt` & `walletv2.txt`)
- Preview saldo semua akun sebelum eksekusi (real-time dari RPC)
- Eksekusi paralel per-batch menggunakan `ThreadPoolExecutor`
- Retry otomatis dengan backoff saat RPC mengembalikan error rate limit
- Jeda acak antar batch untuk menghindari spam RPC
- Ringkasan hasil + log lengkap tersimpan ke `results.json`
- Output terminal berwarna (colorama)

## 📋 Persyaratan

- Python 3.9+
- Koneksi ke RPC jaringan Pharos (atau RPC kompatibel EVM lainnya)

## 🚀 Instalasi

1. **Clone repository**
   ```bash
   git clone https://github.com/username/pharos-mainnet-sender.git
   cd pharos-mainnet-sender
   ```

2. **(Opsional) Buat virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install web3 eth-account python-dotenv colorama
   ```

   Atau buat `requirements.txt` berisi:
   ```
   web3
   eth-account
   python-dotenv
   colorama
   ```
   lalu jalankan `pip install -r requirements.txt`

4. **Siapkan file konfigurasi `.env`**
   ```env
   RPC_URL=https://rpc.pharos.xyz
   TO_ADDRESS=0xAlamatTujuanAnda
   DELAY_MIN=1
   DELAY_MAX=3
   WALLET_FILE=wallet.txt
   WALLET_FILE2=walletv2.txt
   MAX_WORKERS=3
   MAX_RETRY=3
   RETRY_DELAY=5
   ```

5. **Siapkan file wallet** (`wallet.txt` dan/atau `walletv2.txt`)

   Satu baris = satu wallet. Bisa berupa private key atau seed phrase:
   ```
   0xabc123...def456
   word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12
   # baris diawali # akan diabaikan
   ```

6. **Jalankan script**
   ```bash
   python main.py
   ```

## 🔁 Alur Kerja (Flow)

1. **Banner & konfigurasi** — script menampilkan ringkasan konfigurasi (RPC, alamat tujuan, jumlah thread, retry, delay).
2. **Load wallet** — membaca `wallet.txt` dan `walletv2.txt`, memvalidasi tiap baris (private key hex 64 karakter atau seed phrase), lalu men-derive address-nya.
3. **Koneksi Web3** — menghubungkan ke RPC dan memverifikasi koneksi + chain ID.
4. **Preview saldo** — mengambil saldo tiap akun secara real-time dan menampilkan tabel (address, sumber, saldo, status siap/kosong), termasuk total saldo gabungan.
5. **Konfirmasi manual** — pengguna harus mengetik `YA` untuk melanjutkan proses pengiriman (safety check).
6. **Eksekusi paralel per-batch**:
   - Semua akun dibagi ke dalam batch sesuai `MAX_WORKERS`.
   - Tiap batch diproses bersamaan lewat `ThreadPoolExecutor`.
   - Untuk tiap akun: hitung gas price & gas cost, kirim seluruh saldo (`saldo - biaya gas`) ke `TO_ADDRESS`, lalu tunggu receipt transaksi.
   - Jika RPC mengembalikan error rate limit (429), otomatis retry dengan jeda meningkat.
   - Ada jeda acak (`DELAY_MIN`–`DELAY_MAX` detik) antar batch.
7. **Ringkasan akhir** — menampilkan jumlah transaksi sukses/gagal/dilewati/error beserta total dana yang berhasil terkirim, dan menyimpan detail lengkap ke `results.json`.

## ⚠️ Peringatan Keamanan

- **Jangan pernah** commit file `.env`, `wallet.txt`, atau `walletv2.txt` ke repository — file-file ini berisi kunci privat/seed phrase yang bisa digunakan untuk mengambil alih dana.
- Tambahkan ke `.gitignore`:
  ```
  .env
  wallet.txt
  walletv2.txt
  results.json
  venv/
  ```
- Gunakan script ini hanya pada wallet milik sendiri. Pastikan `TO_ADDRESS` sudah benar sebelum konfirmasi, karena transaksi di blockchain bersifat final dan tidak bisa dibatalkan.

## 📄 Lisensi

Tambahkan lisensi sesuai kebutuhan Anda (misalnya MIT).
