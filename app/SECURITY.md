# BIG PAW security notes

Implemented in the v1.0 system build:
- PBKDF2 password hashing with per-user salts
- expiring bearer sessions
- role-based authorization (buyer / breeder / operator)
- ownership checks for breeder health records and uploads
- listing moderation before public visibility
- upload MIME/size restrictions
- login/reset request rate limiting
- security response headers + restrictive same-origin CSP
- audit log for sensitive operations
- password reset invalidates existing sessions
- operator-triggered SQLite backups

Before Internet launch:
- replace browser localStorage bearer-token storage with a hardened production auth design (recommended HttpOnly Secure SameSite cookies + CSRF protection)
- use HTTPS only
- connect email, payments, object storage and monitoring providers
- run dependency/infrastructure security review and penetration testing
- rotate/remove all demo credentials
- configure off-site encrypted backups and restore drills
