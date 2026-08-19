# Employee Schedule Portal

A polished Flask employee schedule portal inspired by the provided Stop & Shop-style reference.

## Included

- Responsive desktop + mobile UI
- Mobile navigation that locks the page and uses a modal backdrop
- Employee ID + password login
- SQLite database (`schedule_portal.db`)
- Passwords stored as secure Werkzeug password hashes, never plaintext
- Forced password change on first login
- Administrator role
- Administrator dashboard
- Schedule PDF publishing
- Employee user management
- Add/edit/disable users
- Password reset to the temporary password
- Current + optional next-week schedule PDFs
- Backend designed to be easy to connect to a real employee system

## First-run accounts

The database is created automatically when the app starts.

Administrator:

- Employee ID: `admin`
- Temporary password: `password`

The admin is forced to change the password on first login.

New employees created by an administrator also receive:

- Temporary password: `password`
- Forced password change on first login

## Run locally

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Schedule files

The app uses:

- `uploads/current.pdf`
- `uploads/next_week.pdf`

Administrators can publish these through the Administration → Schedule Uploads page.

## Database

SQLite is used intentionally because it is simple to deploy and easy to replace later.

The `users` table contains:

- employee ID
- name
- job title
- role
- password hash
- forced-password-change flag
- active/disabled status
- creation timestamp

Passwords use `werkzeug.security.generate_password_hash()` and `check_password_hash()`.

## Production checklist

Before deploying publicly:

1. Set a strong random `SECRET_KEY`.
2. Run behind HTTPS.
3. Put Flask behind Nginx or another production WSGI setup.
4. Back up `schedule_portal.db`.
5. Restrict administrator accounts carefully.
6. Consider CSRF protection for production forms.
7. Consider rate limiting login attempts.
8. Replace the SQLite user lookup with your actual employee/authentication system if appropriate.
9. Consider object storage for PDFs if there will be many stores/locations.
10. Never keep the temporary password as a permanent credential.

## Fixed in this version

The forced password-change page now correctly renders as a standalone authentication page even though the user is already logged in.
