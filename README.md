# Bot_ShieldDuration - Telegram Shield Reminder Bot

Ini paket siap-deploy untuk bot Telegram *Bot_ShieldDuration* yang mengingatkan shield Lords Mobile:
- Notifikasi 1 jam sebelum habis
- Notifikasi 5 menit sebelum habis
- Notifikasi saat habis
- Ringkasan harian (pukul 08:00 server)
- Multi-user (sampai 20 akun per user)

## Cara pakai (singkat)
1. Extract zip.
2. Isi file `.env` dengan token bot kamu: `BOT_TOKEN=...`
3. Deploy ke Render (atau Railway) dan jalankan `python main.py`.

## Command di Telegram
- `/start` - memulai bot
- `/setshield <nama_akun> <durasi> <jam>` - contoh: `/setshield NalaWuxin 7days 02:45`
- `/listshield` - lihat semua shield yang diset
- `/removeshield <nama_akun>` - hapus pengingat untuk akun

