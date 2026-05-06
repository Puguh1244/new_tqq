# Rekap Nilai Per Kelas Asli - Modern Web App

Aplikasi web modern untuk memproses file Excel rekap nilai mahasiswa menjadi output Excel multi-sheet berdasarkan **KODE KELAS PAI asli**.

## Stack

Frontend:
- Next.js
- React
- TypeScript
- Tailwind CSS
- Recharts
- Lucide React

Backend:
- FastAPI
- pandas
- openpyxl
- rapidfuzz
- Groq SDK opsional
- python-dotenv

## Struktur

```text
frontend/
backend/
```

## Menjalankan backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Menjalankan frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Buka:

```text
http://localhost:3000
```

Backend default:

```text
http://localhost:8000
```

## Environment backend

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ganti-dengan-password-kuat
APP_AUTH_TOKEN=ganti-dengan-token-random-panjang
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
FRONTEND_ORIGINS=http://localhost:3000
```

## Environment frontend

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Deploy

Frontend ke Vercel:
- Set root directory ke `frontend`
- Set env `NEXT_PUBLIC_API_BASE_URL` ke URL backend production

Backend ke Render/Railway:
- Root directory `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set `GROQ_API_KEY` hanya di backend
- Wajib set `ADMIN_PASSWORD` kuat dan jangan memakai password default `admin123` di backend deploy
- Set `APP_AUTH_TOKEN` ke nilai random panjang agar token admin tetap stabil antar restart

## Catatan penting

- Nama typo tidak difinalkan tanpa approval user.
- Data yang tidak cocok tetap masuk audit.
- Kolom `NO` di setiap sheet kelas dibuat ulang mulai dari 1.
- Sheet kelas final bersih dari kolom teknis audit.
- Sheet audit tetap lengkap.
