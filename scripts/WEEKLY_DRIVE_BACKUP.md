# Weekly BIG PAW offsite backup — deployment checklist

Status: PROPOSED ONLY. The utility in `scripts/weekly_drive_backup.py` is not
installed, scheduled, or connected to the live BIG PAW service.

## Important: Google Drive authentication

A Google service account generally cannot create files in a normal personal
"My Drive" folder because it has no storage quota. **Do not deploy this version
against the owner's ordinary My Drive folder without first validating a
supported authentication/storage configuration.** The current script expects
Application Default Credentials from a service account and is appropriate
only when the destination is a Shared Drive that allows service-account writes,
or another explicitly verified configuration.

The owner-selected folder ID is
`1HU8KMz1n1ZmiiV67RR69u73UpwCHva0r`. Its Shared Drive eligibility has
not been verified.

## Required before any production change

1. Select and verify a supported Drive authorization method. For a personal
   My Drive destination, prefer user-authorized OAuth credentials with refresh
   token stored in Railway secrets, not in GitHub.
2. Verify that the Railway persistent volume contains the live SQLite DB
   and determine its exact path; do not guess from the repository layout.
3. Install `google-auth` and `google-api-python-client` in a separate
   scheduled service/image, without changing the existing web service.
4. Provide credentials via protected secret/file mounts. Never commit keys,
   refresh tokens, SQLite files, or user data to this public repository.
5. Configure a weekly Monday cron schedule in the deployment platform.
6. Test against a non-production database and a test Drive folder; check
   SQLite `PRAGMA integrity_check`, uploaded size, and restoration.
7. Test retry/duplicate behavior and failure notifications.
8. Confirm the production upload exists in Drive before claiming success.

## Existing behavior preserved

The web server's existing automatic local backup and retention are not
modified. No operator auth bypass or unauthenticated download endpoint is added.
