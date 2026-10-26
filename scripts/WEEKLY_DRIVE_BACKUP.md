# BIG PAW — weekly Google Drive offsite backup

**Status: draft, not deployed or scheduled.** This change does not affect the existing local automatic backup.

## Authorization for personal Google Drive

Use Google OAuth user consent and a refresh token, not a service account. The
Google Cloud OAuth app must enable Google Drive API. Authorize the exact
`https://www.googleapis.com/auth/drive` scope and obtain a refresh token
using a trusted OAuth flow. Note: in OAuth **Testing** mode, refresh tokens may
expire after seven days. Configure the consent screen and verification/publication
as appropriate before relying on unattended backups.

Never paste OAuth client secrets or refresh tokens into GitHub, public chat,
commits, screenshots, or documentation. Store all secrets in Railway's protected
environment variables. Revoke credentials immediately if exposed.

Target Drive folder:
`1HU8KMz1n1ZmiiV67RR69u73UpwCHva0r` (BIG PAW Backups).
Verify that the OAuth user can write to this folder.

## Required Railway configuration (not yet performed)

Use a dedicated scheduled worker **with access to the same persistent SQLite
volume** as the web service, if the hosting platform supports safe volume
sharing. Railway volumes are typically mounted to a single service; verify
this first. If sharing is not supported, design a safe alternative rather
than guessing the DB path or copying a stale database from source control.

Required variables:
- `BIGPAW_DB_PATH`: verified path to the production SQLite database
- `BIGPAW_DRIVE_FOLDER_ID`: folder ID above
- `BIGPAW_GOOGLE_CLIENT_ID`: OAuth client ID
- `BIGPAW_GOOGLE_CLIENT_SECRET`: OAuth client secret
- `BIGPAW_GOOGLE_REFRESH_TOKEN`: OAuth refresh token

Python packages: `google-auth`, `google-api-python-client`.
Command: `python scripts/weekly_drive_backup.py`.
Desired schedule: Monday weekly (timezone explicitly set/verified).

## Production release gate

1. Confirm volume access and user-authorized Drive write permissions.
2. Run local test on a temporary SQLite database (no production records).
3. Run upload test to a separate test folder; check file size and restore it.
4. Verify failure handling, retries, logs, and notification ownership.
5. Only then enable production scheduling and verify a real upload.

No public backup URL, weakened operator login, or production change is needed
for this draft. Never claim automatic protection until a real Drive file is
verified after the scheduled run.

## Verified from source code

The live application's SQLite path is selected by `BIGPAW_DATA_DIR`:
if set, `<BIGPAW_DATA_DIR>/bigpaw.sqlite3`; otherwise `app/backend/bigpaw.sqlite3` in the container. This is source-code behavior, **not** confirmation of Railway's actual environment or volume mount. Do not run an isolated cron service without verifying access to the same persistent volume. A safe alternative is a minimal background timer in the existing web process, gated by opt-in environment variables, but it requires careful concurrency and restart tests.

Offline GitHub Actions workflow `Weekly Drive backup safety checks` passed for commit `5818006980ef639e7b16998500e1f3b2892468f1`. This does not test Drive upload.

**Security review:** Existing folder access may require the broader restricted Google Drive OAuth scope (`drive`), rather than `drive.file` which typically limits access to app-created or user-selected files. This is a sensitive permission: confirm explicit owner consent and Google OAuth verification requirements. Do not request credentials in chat. A narrower permission design (e.g. OAuth Picker for the folder or a dedicated new folder) should be evaluated before release.
