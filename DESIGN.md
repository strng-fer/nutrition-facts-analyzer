# Design Direction: Sistem Informasi Nilai Gizi (Nutrition Facts Extractor)

> Reading this as: Web Application Tool (Nutrition Facts AI Extractor) for health researchers, consumers, and food industry analysts, in a professional academic/clinical nutrition editorial style inspired by ITERA portal standards, dial ENERGY 2 / RHYTHM 2 / MOTION 1.

## 1. Identity & Character
- **Product Context**: Sistem ekstraksi dan digitalisasi tabel Informasi Nilai Gizi dari kemasan produk pangan secara otomatis menggunakan deteksi Computer Vision, OCR, dan restrukturisasi AI.
- **Inspirasi & Tone**: Terinspirasi dari kesederhanaan, otoritas, dan kejelasan portal akademik dan kesehatan (seperti SIYUDIS ITERA): lugas, berstruktur jelas, tepercaya, bebas dari ornamen generik, dan fokus pada kegunaan data.
- **Dial**:
  - `ENERGY: 2` (Balanced: percaya diri, profesional, kredibel tanpa berteriak)
  - `RHYTHM: 2` (Consistent with purposeful section breaks: pembagian 2 kolom terstruktur)
  - `MOTION: 1` (Subtle: transisi status yang halus tanpa animasi floating/bouncing berlebih)

## 2. Color Palette & Hierarchy
- **Primary Brand (Emerald Green)**:
  - `--emerald-700: #047857`, `--emerald-600: #059669`, `--emerald-500: #10b981`
  - *Alasan*: Merepresentasikan nutrisi nabati segar, kesehatan pangan, vitalitas, serta standar kredibilitas institusi.
- **Accent (Warm Amber)**:
  - `--amber-600: #d97706`, `--amber-500: #f59e0b`
  - *Alasan*: Menandai informasi energi dan kalori penting agar langsung terlihat oleh pengguna.
- **Dual Themes**:
  - **Mode Gelap (Dark)**: Latar `#0b1118` dengan kontras teks putih `#f8fafc` dan slate terang `#cbd5e1`.
  - **Mode Terang (Light)**: Latar `#f8fafc` dengan teks deep slate `#0f172a` (kontras WCAG AA > 10:1).

## 3. Background Imagery
- Foto komersial resolusi tinggi bertema bahan pangan bernutrisi sehat (sayuran hijau segar, alpukat, beri, jeruk, dan biji-bijian) dengan *subtle overlay gradient* untuk memastikan kontras teks 100% terbaca sesuai standar aksesibilitas WCAG AA.
- Tidak menggunakan pola titik/grid blueprint artifisial atau lingkaran neon generik.

## 4. Typography
- **Primary Interface**: `Plus Jakarta Sans` (bobot 400, 500, 600, 700) untuk keterbacaan teks dan instruksi yang ramah namun formal.
- **Numerical & Code Output**: `JetBrains Mono` khusus untuk metrik nutrisi, nilai numerik, persentase AKG, dan data JSON/OCR mentah.

## 5. Craftsmanship & Accessibility
- **WCAG AA Compliance**: Semua teks memiliki rasio kontras minimal 4.5:1.
- **Keyboard Navigation**: Dropzone, tombol, input, dan akordeon dapat diakses dengan `Tab`, `Enter`, `Space`, dan `Escape`.
- **Tap Targets**: Seluruh elemen tombol interaktif memiliki tinggi minimal 44px untuk kenyamanan perangkat layar sentuh dan mobile.
- **Bebas Em Dash**: Menghindari karakter em dash (`—`) pada seluruh teks antarmuka sesuai aturan anti-slop.
