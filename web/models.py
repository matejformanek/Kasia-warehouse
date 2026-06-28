"""The public marketing site has no models.

The former ``ContactInquiry`` (poptávkový formulář store) was removed in
decision 0052 — Kontakt is now an info-only page (direct phone/e-mail + an
executive directory + a map), so the public site stores no user data. The
table is dropped by migration ``0002_delete_contactinquiry``.
"""
