"""One-time setup: get a long-lived Dropbox refresh token for dropbox_sync.py.

Usage:
    DROPBOX_APP_KEY=<your app key> uv run dropbox_auth.py

Uses the PKCE flow, so the app secret is never needed.
"""

import os
import sys

from dropbox import DropboxOAuth2FlowNoRedirect  # pyright: ignore[reportMissingTypeStubs]


def main() -> None:
    app_key = os.environ.get("DROPBOX_APP_KEY")
    if not app_key:
        sys.exit("Set DROPBOX_APP_KEY first (from your app's page in the Dropbox App Console).")

    flow = DropboxOAuth2FlowNoRedirect(app_key, use_pkce=True, token_access_type="offline")
    print("1. Open this URL and click Allow:\n")
    print(f"   {flow.start()}\n")
    code = input("2. Paste the code Dropbox shows you: ").strip()

    result = flow.finish(code)  # pyright: ignore[reportUnknownMemberType]
    print("\n3. Add this line to .envrc (it is gitignored), then run `direnv allow`:\n")
    print(f'   export DROPBOX_REFRESH_TOKEN="{result.refresh_token}"')


if __name__ == "__main__":
    main()
