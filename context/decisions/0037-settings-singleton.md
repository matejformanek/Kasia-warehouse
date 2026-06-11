# 0037 — Settings model: enforced singleton, write-only password, FileField logo

## Context

[`../screens/14-nastaveni.md`](../screens/14-nastaveni.md) describes
the Nastavení screen as "a small, calm place" for a fixed set of
configuration values: company-header identity, SMTP credentials,
the fixed dodák recipient pair (Petr + Karolína) per
[`0031`](./0031-emails-internal-only-supersedes-0009.md), and the
ratified Czech e-mail templates per
[`0007`](./0007-auto-reissue-corrected-dodaky.md).

There is exactly one such configuration object in the system. The
Pass 2 plan needs three small choices nailed before the migration
lands:

1. **How "single-row" is enforced** at the DB layer. Django has
   no built-in singleton; `pk=1` magic, `Meta.unique_together`
   tricks, and `OneToOneField` to a sentinel are all on the
   menu.
2. **How the SMTP password is stored and rendered.** Screen 14
   says passwords are write-only — never displayed back. That
   covers the UI; the storage shape (plaintext vs. encrypted)
   needs its own line.
3. **Where the company logo lives.** `FileField` on the filesystem,
   `ImageField` with size checks, blob in the database, or
   external storage. The Pass 2 plan picks one; the constraint is
   that Pass 2 doesn't add new dependencies and doesn't require
   Petr's logo files to exist (Matej-ratified 2026-06-04: text
   placeholder is the MVP default).

## Options considered

### (1) Singleton enforcement

- **(a) `singleton_key` field + `UniqueConstraint`.** A
  `CharField(default="singleton", editable=False)` plus
  `UniqueConstraint(fields=["singleton_key"])`. A `Settings.load()`
  classmethod does `get_or_create(singleton_key="singleton")[0]`.
  Schema-level guarantee; survives any path that bypasses the
  classmethod.
- **(b) `pk=1` convention.** Override `save()` to force `pk=1`;
  override `delete()` to no-op. Works but the magic is invisible
  in the schema; a stray `Settings.objects.create()` with no
  override-aware caller can still slip a second row in.
- **(c) `django-solo` package.** Off-the-shelf. Adds a dependency
  for ~15 lines of code; we already have everything we need in
  the ORM.

### (2) SMTP password storage

- **(a) Plaintext `CharField`; admin form uses
  `PasswordInput(render_value=False)` so the value never returns
  to the rendered HTML.** Stored as-is on disk. Same exposure
  surface as the `.env`-driven `EMAIL_HOST_PASSWORD` that already
  exists in `kasia/settings/base.py`. Operator can edit by typing
  a new value; saving with an empty input leaves the existing
  value untouched (Django form convention).
- **(b) Encrypted-at-rest** via `django-fernet-fields` or a custom
  field with a key from `.env`. Adds a dependency, a key
  management story, and a backup-restore concern (lose the key,
  lose the password). Marginal gain at MVP scale (one row, one
  process, on-disk SQLite/Postgres already needs filesystem
  protection for the data itself).
- **(c) Defer to env only.** Don't store the password in the DB at
  all; read `EMAIL_HOST_PASSWORD` from `.env`. Loses the screen-14
  "edit from UI" affordance.

### (3) Logo storage

- **(a) `FileField(upload_to="logos/")`** on the filesystem under
  `MEDIA_ROOT`. Django built-in; no extra dependency. WeasyPrint
  reads the file URL directly. `MEDIA_ROOT` + `MEDIA_URL` are
  added to `kasia/settings/base.py` in this pass.
- **(b) `ImageField` + Pillow.** Same shape as (a) but with image
  validation (dimensions, content sniff). Adds Pillow as a
  dependency; the MVP doesn't actually need dimension checks
  beyond what the browser-side `accept="image/*"` already does.
- **(c) `BinaryField` in the database.** No filesystem dependency
  at deploy. But the backup story for `MEDIA_ROOT` is the same
  story as for everything else operator-uploaded (volume mount on
  the Hetzner box), so this gains nothing.

## Choice

### (1) `singleton_key` field + `UniqueConstraint`.

```python
class Settings(models.Model):
    singleton_key = models.CharField(
        max_length=16, default="singleton", editable=False,
    )
    # … all other fields per screens/14 …

    class Meta:
        verbose_name = "nastavení"
        verbose_name_plural = "nastavení"
        constraints = [
            UniqueConstraint(fields=["singleton_key"], name="settings_singleton"),
        ]

    @classmethod
    def load(cls) -> "Settings":
        obj, _ = cls.objects.get_or_create(singleton_key="singleton")
        return obj
```

`SettingsAdmin.has_add_permission` returns `False` once a row
exists; `has_delete_permission` returns `False` always. The seed
migration `inventory/0005_seed_settings.py` inserts the row with
the Matej-ratified defaults (recipient pair left blank
intentionally — operator fills them on first run).

### (2) Plaintext `CharField` with write-only admin widget.

```python
smtp_password = models.CharField("SMTP heslo", max_length=128, blank=True)
```

`SettingsAdmin` overrides `formfield_overrides` (or the form's
`__init__`) so that `smtp_password`'s widget is
`PasswordInput(render_value=False)`. An empty input on save means
"do not change"; a non-empty input replaces the value.

Encryption is a future-decision concern. The exposure surface is
identical to the env-driven SMTP credential the system already
trusts; the screen-14 affordance is the gain. If at some later
point the threat model changes (e.g. multi-tenant, or the box
moves), a numbered file can introduce
`django-fernet-fields` or its equivalent and migrate the column.

### (3) `FileField(upload_to="logos/", blank=True)` under `MEDIA_ROOT`.

```python
logo = models.FileField("logo", upload_to="logos/", blank=True)
```

Add to `kasia/settings/base.py`:

```python
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
```

No new dependency. The PDF template falls back to a text
placeholder (`{{ settings.company_name }}`) when `logo` is empty —
the Matej-ratified MVP default per
[`../state.md`](../state.md) 2026-06-04. When Petr supplies SVG
or PDF marks, Karolína uploads via Nastavení; the next render
picks them up.

## Rationale

- **(1)** A constraint on a real column is the only enforcement
  that survives every code path (admin, shell, migrations,
  tests). `django-solo` is fine but doesn't add anything once the
  `load()` classmethod is in place; one fewer dependency to track
  in [`0014`](./0014-language-python-uv.md)-land.
- **(2)** The threat model for ~6 users on one Hetzner box, with
  the `.env` already carrying the SMTP password as plaintext, is
  not improved by encrypting one DB column. Adding encryption
  later is an additive migration; removing it later is friction
  with no payoff. Matches the bias in
  `.claude/rules/right-sized-for-small-business.md`.
- **(3)** Django built-in; no Pillow; matches the deferred-logo
  reality. `MEDIA_ROOT` + `MEDIA_URL` are minor additions to
  `base.py` (Django docs canonical). The Hetzner backup story
  already covers persistent volumes per
  [`0027`](./0027-hosting-hetzner.md), so the logo file is backed
  up with the rest of the operator-uploaded data.

## Date & by-whom

2026-06-11 — Matej (acting as Petr's stand-in per
[`memory/user_role_kasia.md`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/user_role_kasia.md)).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory.Settings` ships in
  `inventory/0004_dodaci_list_and_settings.py` with the
  `singleton_key` + `UniqueConstraint` shape.
- Seed migration `inventory/0005_seed_settings.py` inserts the
  Matej-ratified defaults from
  [`../screens/14-nastaveni.md`](../screens/14-nastaveni.md);
  recipient pair left empty.
- `SettingsAdmin` registers with
  `has_add_permission` gated on row count and
  `has_delete_permission = False`. SMTP password field uses
  `PasswordInput(render_value=False)`.
- `kasia/settings/base.py` gains `MEDIA_URL` + `MEDIA_ROOT`.

**Forecloses (without follow-on decision):**

- `pk=1` singleton pattern. To switch, write a file naming the
  scenario that justifies the bare `Settings.objects.get(pk=1)`
  shape over `Settings.load()`.
- `django-solo` dependency.
- Encrypting `smtp_password` at rest. To add it later, write a
  file that names the threat model that requires it.
- `ImageField` validation. To tighten, write a file that names
  the failure mode (over-large uploads, malicious payloads) that
  justifies adding Pillow.

**Resolves:**

- The Pass 2 plan's "decisions to draft inside this pass" item 2.
