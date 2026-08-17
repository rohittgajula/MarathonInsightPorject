#!/usr/bin/env python3
"""Log in to Garmin and actually persist the session tokens.

Why this exists instead of `garmin-mcp login`:

garmin-mcp 0.4.0 builds its client with `return_on_mfa=True`. In garminconnect
0.3.x that makes `Garmin.login()` take an early-return branch which never writes
the tokenstore:

    if self.return_on_mfa:
        mfa_status, _legacy_token = self.client.login(...)
        return mfa_status, _legacy_token      # <- no dump
    ...
    self.client.dump(tokenstore_path)         # <- only when return_on_mfa is False

garmin-mcp then only calls `dump()` inside its `needs_mfa` branch. On an account
*without* MFA neither path runs, so a completely successful login writes nothing —
and the CLI prints "Logged in." regardless. The result is an empty token directory
and a confident success message.

This script uses the default (return_on_mfa=False) path so the library persists the
tokens itself, handles MFA via prompt, and then *verifies* the directory is non-empty
before claiming anything.

The password is read with getpass, is never echoed, never logged, and never stored —
only the refreshable OAuth token is written to disk.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

DEFAULT_TOKEN_DIR = Path.home() / "Library" / "Caches" / "garmin-mcp" / "garth"


def main() -> int:
    try:
        from garminconnect import Garmin
    except ImportError:
        print("garminconnect is not installed. Run this with the venv interpreter:")
        print("  ~/.garmin-mcp-venv/bin/python scripts/garmin_login.py")
        return 2

    token_dir = Path(os.environ.get("GARMIN_TOKEN_DIR", DEFAULT_TOKEN_DIR)).expanduser()
    token_dir.mkdir(parents=True, exist_ok=True)

    email = os.environ.get("GARMIN_EMAIL") or input("Garmin email: ").strip()
    password = os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Garmin password: ")
    if not email or not password:
        print("Email and password are both required.", file=sys.stderr)
        return 1

    print(f"\nLogging in… tokens will be written to {token_dir}")
    print("If the first strategies report 429, that is normal — the library falls")
    print("through to one that bypasses the rate limit.\n")

    # return_on_mfa is deliberately left at its default of False so that
    # Garmin.login() reaches its own dump() call.
    client = Garmin(email=email, password=password, prompt_mfa=lambda: input("MFA code: ").strip())

    try:
        client.login(str(token_dir))
    except Exception as exc:  # noqa: BLE001 — report the real reason, whatever it is
        print(f"\nLogin failed: {exc}", file=sys.stderr)
        return 1
    finally:
        del password

    # Never trust the absence of an exception — check the tokens are really on disk.
    written = sorted(p.name for p in token_dir.iterdir() if p.is_file())
    if not written:
        print("\nLogin returned without error but wrote no tokens.", file=sys.stderr)
        print(f"{token_dir} is still empty — treat this as a failure.", file=sys.stderr)
        return 1

    print(f"Wrote {len(written)} token file(s): {', '.join(written)}")

    try:
        name = client.get_full_name()
        print(f"Verified against the Garmin API — signed in as {name}.")
    except Exception as exc:  # noqa: BLE001
        print(f"Tokens written, but the API probe failed: {exc}", file=sys.stderr)
        return 1

    print("\nDone. Press 'Refresh Garmin' in Run Project to pull your activities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
