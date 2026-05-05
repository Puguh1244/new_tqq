-- Jalankan SQL ini di Supabase SQL Editor.
-- Table ini dipakai backend untuk menyimpan data pencarian NIM publik.

create table if not exists public_lookup (
  id bigserial primary key,
  nim text not null unique,
  nama text,
  kode_kelas_pai text,
  data jsonb not null,
  updated_at timestamptz default now()
);

create index if not exists public_lookup_nim_idx on public_lookup (nim);
