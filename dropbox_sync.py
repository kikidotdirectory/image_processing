"""Convert the PSDs in a Dropbox folder and upload the watermarked JPGs to another.

Usage:
    uv run dropbox_sync.py /Art/PSDs /Art/Exports

Needs DROPBOX_APP_KEY and DROPBOX_REFRESH_TOKEN in the environment (see dropbox_auth.py).
PSDs whose contents haven't changed since the last successful run are skipped; the
record of what has been done is kept in out/.dropbox_state.json.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import cast

import dropbox  # pyright: ignore[reportMissingTypeStubs]
from dropbox.files import (  # pyright: ignore[reportMissingTypeStubs]
    FileMetadata,
    ListFolderResult,
    Metadata,
    WriteMode,
)

from main import OUT_DIR, convert_psd_to_jpg

STATE_FILE = OUT_DIR / ".dropbox_state.json"


def connect() -> dropbox.Dropbox:
    app_key = os.environ.get("DROPBOX_APP_KEY")
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    if not app_key or not refresh_token:
        sys.exit("Set DROPBOX_APP_KEY and DROPBOX_REFRESH_TOKEN (run dropbox_auth.py to get the token).")
    return dropbox.Dropbox(app_key=app_key, oauth2_refresh_token=refresh_token)


def list_psds(dbx: dropbox.Dropbox, folder: str) -> list[FileMetadata]:
    # The SDK is untyped and basedpyright infers these calls return None, hence the
    # cast through `object` to the result type the Dropbox docs specify.
    res = cast(ListFolderResult, cast(object, dbx.files_list_folder(folder)))  # pyright: ignore[reportUnknownMemberType]
    entries = cast(list[Metadata], res.entries)
    while cast(bool, res.has_more):
        res = cast(ListFolderResult, cast(object, dbx.files_list_folder_continue(res.cursor)))  # pyright: ignore[reportUnknownMemberType]
        entries += cast(list[Metadata], res.entries)
    return [
        e for e in entries
        if isinstance(e, FileMetadata) and cast(str, e.name).lower().endswith(".psd")
    ]


def load_state() -> dict[str, str]:
    try:
        return cast(dict[str, str], json.loads(STATE_FILE.read_text()))
    except FileNotFoundError:
        return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ = STATE_FILE.write_text(json.dumps(state, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("src", help="Dropbox folder with PSDs, e.g. /Art/PSDs")
    _ = parser.add_argument("dest", help="Dropbox folder to upload JPGs to, e.g. /Art/Exports")
    _ = parser.add_argument("--force", action="store_true", help="reconvert even unchanged PSDs")
    args = parser.parse_args()
    src, dest, force = cast(str, args.src), cast(str, args.dest).rstrip("/"), cast(bool, args.force)

    dbx = connect()
    state = load_state()
    psds = list_psds(dbx, src)
    print(f"Found {len(psds)} PSD(s) in {src}")

    failed: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for psd in psds:
            path = cast(str, psd.path_display)
            content_hash = cast(str, psd.content_hash)
            if not force and state.get(path) == content_hash:
                print(f"  skip     {path} (unchanged)")
                continue

            print(f"  convert  {path}")
            local_psd = Path(tmp) / cast(str, psd.name)
            try:
                dbx.files_download_to_file(str(local_psd), cast(str, psd.path_lower))  # pyright: ignore[reportUnknownMemberType]
                for jpg in convert_psd_to_jpg(local_psd):
                    _ = dbx.files_upload(  # pyright: ignore[reportUnknownMemberType]
                        jpg.read_bytes(), f"{dest}/{jpg.name}", mode=WriteMode.overwrite
                    )
                    print(f"    -> {dest}/{jpg.name}")
            except Exception as exc:  # noqa: BLE001  # keep going so one bad file doesn't stop the batch
                print(f"    FAILED: {exc}", file=sys.stderr)
                failed.append(path)
                continue
            finally:
                local_psd.unlink(missing_ok=True)  # PSDs are large; don't let them pile up

            state[path] = content_hash
            save_state(state)

    if failed:
        sys.exit(f"{len(failed)} file(s) failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
