# PS3 Cache API (NAS MVP)

Eigenständiger NAS-Dienst zur Verwaltung und lokalen Zwischenspeicherung von **legalen PS3-Backups** für eine PS3 mit CFW.

Wichtig: Dieses Projekt ersetzt **nicht** `ps3netsrv`, sondern stellt eine neue Architektur bereit:

- FastAPI-Service auf dem NAS
- SQLite-basierte Persistenz + Queue
- Background Worker für Cache-Kopierjobs
- optionaler webMAN-Trigger nach erfolgreicher Übertragung
- vorbereitet für spätere PS3-Homebrew-App oder Web-Frontend

## 1. Projektidee

Das MVP fokussiert auf die NAS-Seite:

1. API bereitstellen
2. ISO-Sammlung auf dem NAS indizieren
3. Targets (PS3-Ziele) verwalten
4. Job-Queue verwalten
5. Job-Fortschritt und Status ausgeben
6. Optional nach Erfolg webMAN antriggern

## 2. Architektur

### Komponenten

- `FastAPI` als REST-API
- `SQLite` als zentrale Persistenz
- `WorkerManager` im selben Container (ein aktiver Job gleichzeitig)
- `GameScanner` für rekursiven Scan von `.iso`, `.bin`, `.cue`, `.pkg` im Library-Ordner
- `FtpTransport` über `TargetTransport`-Abstraktion
- `WebmanService` als gekapselter HTTP-Trigger

### Datenmodell

- `games`: indizierte ISOs inkl. Metadaten-Heuristik
- `targets`: PS3-Ziele inkl. FTP-Infos und Kapazitätsschätzung
- `jobs`: Queue + Laufstatus + Fortschritt
- `job_events`: Ereignis-Historie pro Job

### Worker-Verhalten (MVP)

- genau 1 aktiver Kopierjob
- weitere Jobs bleiben `queued`
- chunkweise FTP-Übertragung mit Fortschritts-Updates
- Cancel-Flag wird periodisch geprüft
- Retry-Struktur vorhanden (`attempt_count` + `max_retries`)
- Für PS3-Dateien wird eine vorhandene Sidecar-`*.key` automatisch mit übertragen

## 3. Verzeichnisstruktur

```text
.
├── .dockerignore
├── .env.example
├── Dockerfile
├── README.md
├── app
│   ├── api
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes
│   │       ├── games.py
│   │       ├── health.py
│   │       ├── jobs.py
│   │       ├── scan.py
│   │       └── targets.py
│   ├── core
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db
│   │   ├── base.py
│   │   ├── init_db.py
│   │   └── session.py
│   ├── main.py
│   ├── models
│   │   ├── game.py
│   │   ├── job.py
│   │   ├── job_event.py
│   │   └── target.py
│   ├── schemas
│   │   ├── game.py
│   │   ├── health.py
│   │   ├── job.py
│   │   ├── scan.py
│   │   └── target.py
│   ├── services
│   │   ├── metadata.py
│   │   ├── scanner.py
│   │   ├── transports
│   │   │   ├── base.py
│   │   │   └── ftp.py
│   │   └── webman.py
│   └── worker
│       └── manager.py
├── config
├── data
├── docker-compose.yml
├── logs
├── requirements.txt
└── scripts
    └── create_cache_job.py
```

## 4. Start unter Docker Compose auf OMV

### Voraussetzungen

- OpenMediaVault mit Docker Compose Plugin oder Docker CLI
- NAS-Pfad mit deinen ISO-Dateien
- optional: PS3 mit aktivem FTP und webMAN

### Schritte

1. Konfiguration erzeugen:

```bash
cp .env.example .env
```

2. In `.env` mindestens `LIBRARY_HOST_PATH` anpassen:

```env
PS3CACHE_IMAGE=ps3cache-api:0.1.0
LIBRARY_HOST_PATH=/srv/dev-disk-by-uuid-XXXX/ps3library
```

3. Image bereitstellen (eine Variante wählen):

Variante A, lokal auf dem OMV-Host bauen:

```bash
docker build -t ps3cache-api:0.1.0 .
```

Variante B, Image aus Registry verwenden:

```env
PS3CACHE_IMAGE=ghcr.io/<dein-user>/ps3cache-api:0.1.0
```

4. Stack starten:

```bash
docker compose up -d
```

5. Health prüfen:

```bash
curl http://<OMV-IP>:8087/health
```

6. Webinterface öffnen:

```text
http://<OMV-IP>:8087/ui
```

## 5. Beispiel `.env`

```env
APP_NAME=ps3cache-api
APP_ENV=production
PS3CACHE_IMAGE=ps3cache-api:0.1.0
API_HOST=0.0.0.0
API_PORT=8080
API_PUBLIC_PORT=8087
DATABASE_URL=sqlite:////data/ps3cache.db
LIBRARY_HOST_PATH=/srv/dev-disk-by-uuid-XXXX/ps3library
LIBRARY_ROOT=/library
LOG_LEVEL=INFO
LOG_DIR=/logs
LOG_FILE_NAME=app.log
SCAN_ON_STARTUP=true
SCAN_RECURSIVE=true
WORKER_POLL_INTERVAL_SEC=2
WORKER_COPY_CHUNK_SIZE=1048576
WORKER_MAX_RETRIES=1
FTP_TIMEOUT_SEC=20
WEBMAN_TIMEOUT_SEC=4
TZ=Europe/Berlin
```

## 6. API-Beispiele (`curl`)

### Healthcheck

```bash
curl http://localhost:8087/health
```

### Manuelles Scannen

```bash
curl -X POST http://localhost:8087/scan
```

Hinweis: `/scan` ist ein `POST`-Endpoint.

### Spiele auflisten

```bash
curl http://localhost:8087/games
```

### Target anlegen

```bash
curl -X POST http://localhost:8087/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wohnzimmer-PS3",
    "ip_address": "192.168.178.50",
    "ftp_port": 21,
    "webman_port": 80,
    "ftp_username": "anonymous",
    "ftp_password": "",
    "target_path": "/dev_hdd0/PS3ISO"
  }'
```

### Kapazität setzen

```bash
curl -X POST http://localhost:8087/targets/1/capacity \
  -H "Content-Type: application/json" \
  -d '{
    "total_bytes": 500000000000,
    "reserved_bytes": 20000000000,
    "used_bytes_estimate": 100000000000
  }'
```

### Cache-Job anlegen

```bash
curl -X POST http://localhost:8087/jobs/cache \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": 1,
    "target_id": 1,
    "auto_mount": true
  }'
```

### Jobs auflisten / Details / Cancel

```bash
curl http://localhost:8087/jobs
curl http://localhost:8087/jobs/1
curl -X POST http://localhost:8087/jobs/1/cancel
```

## 7. CLI-Helfer für Job-Erstellung

Lokal ausführen:

```bash
python3 scripts/create_cache_job.py --api-url http://localhost:8087 --game-id 1 --target-id 1 --auto-mount
```

## 8. Hinweise zur späteren PS3-Homebrew-App

Die spätere App kann direkt auf diese Endpunkte gehen:

- Bibliothek: `GET /games`
- Targets: `GET /targets`
- Jobs starten: `POST /jobs/cache`
- Fortschritt pollen: `GET /jobs/{id}`

Damit kann die Homebrew-App im ersten Schritt als reiner API-Client umgesetzt werden.

## 9. Sicherheit und Robustheit im MVP

- keine Shell-Konstruktion aus API-Parametern
- strukturierte Fehlerantworten (Validation/HTTP/Internal)
- Logs mit Dateirotation
- Zugangsdaten werden nicht in Logs ausgegeben
- Transport über Interface (`TargetTransport`) abstrahiert

## 10. Annahmen (dokumentiert)

1. FTP ist für die Ziel-PS3 erreichbar.
2. Kapazitäten werden im MVP manuell gepflegt (`/targets/{id}/capacity`).
3. webMAN-Trigger nutzt aktuell `GET /mount.ps3<remote_path>`.
4. Zugangsdaten werden in SQLite gespeichert (nicht verschlüsselt, aber nicht geloggt).
5. Scanner verarbeitet `.iso`, `.bin`, `.cue`, `.pkg` (keine `.key`-Einträge in der Spieleliste) und nur Metadaten.

## 11. ARM64 / x86_64

Durch `python:3.12-slim` ist das Image für beide Plattformen praktikabel (sofern Docker-Host die entsprechende Architektur unterstützt).
