import os
import json

from typing import List, Dict, Annotated

from dotenv import load_dotenv
from webdav3.client import Client
from typer import Typer, Argument, Option

app = Typer()


def recursive_ls(
    client: Client, path: str, remote_root: str = ""
) -> List[Dict[str, str]]:
    paths = []

    if remote_root == "":
        remote_root = path

    for f in client.list(path, get_info=True):
        # Get the current local path relative to the root
        current_local_path = f["path"].replace(remote_root + "/", "", 1)
        if current_local_path[0] == "/":
            current_local_path = current_local_path[1:]

        if f["isdir"]:
            paths.extend(recursive_ls(client, f["path"], remote_root))
        else:
            etag = f["etag"]

            # Fix weird behavior of etag
            if (etag[0] == '"' and etag[-1] == '"') or (
                etag[0] == "'" and etag[-1] == "'"
            ):
                etag = etag[1:-1]

            paths.append(
                {
                    "remote_path": f["path"],
                    "remote_etag": etag,
                    "local_path": current_local_path,
                    "local_etag": None,
                }
            )

    return paths


def getenv_with_error(key: str) -> str:
    value = os.getenv(key)
    if value == None:
        raise ValueError(f"[ENV]   {key} is not set")
    return value


@app.command()
def main(
    remote_paths: Annotated[List[str], Argument(help="Remote paths to sync from")],
    local_path: Annotated[str, Argument(help="Local path to sync to")],
    lock_file: Annotated[
        str | None,
        Option(
            help="The path to write the lock file containing current file hashes/eTAGs to. "
            + "Defaults to <local path>/.sync.lock."
        ),
    ] = None,
):
    load_dotenv()

    nextcloud_user = getenv_with_error("NEXTCLOUD_USER")
    nextcloud_password = getenv_with_error("NEXTCLOUD_PASSWORD")
    nextcloud_url = getenv_with_error("NEXTCLOUD_REMOTE")

    # If lock file is not provided, default to <local path>/.sync.lock
    if lock_file == None:
        lock_file = os.path.join(local_path, ".sync.lock")

    print(f"[APP]    Gathered environment variables and options")
    print(f"[APP]    Remote paths:     {", ".join(remote_paths)}")
    print(f"[APP]    Nextcloud user:   {nextcloud_user}")
    print(f"[APP]    Nextcloud URL:    {nextcloud_url}")
    print(f"[APP]    Local path:       {local_path}")
    print(f"[APP]    Lock file:        {lock_file}")

    # Create local path if it doesn't exist
    if not os.path.exists(local_path):
        print(f"[FS]     Creating directory {local_path}")
        os.makedirs(local_path)

    # Load lock file if it exists
    lock_content = {}
    if os.path.exists(lock_file):
        with open(lock_file, "r") as f:
            lock_content = json.load(f)
            print(f"[FS]     Found lock file {lock_file}")

    webdav_client_options = {
        "webdav_hostname": nextcloud_url,
        "webdav_login": nextcloud_user,
        "webdav_password": nextcloud_password,
    }

    webdav_client = Client(webdav_client_options)

    print("[APP]    Starting sync")
    print(f"\n\n[STAGE]  Gathering remote state\n")

    paths = {}
    for remote_path in remote_paths:
        # Add nextcloud WebDAV path as prefix
        remote_path_url = "remote.php/dav/files/" + nextcloud_user + "/" + remote_path

        print(f"[WEBDAV] Getting contents of {remote_path}")
        try:
            for f in recursive_ls(webdav_client, remote_path_url):
                if f["local_path"] in paths:
                    print(
                        f"[WEBDAV] Warning: File {f['local_path']} is present in multiple remote paths"
                    )
                paths[f["local_path"]] = f
        except Exception as e:
            print(f"[WEBDAV] Error: {e}")
            exit(1)

    print(f"\n\n[STAGE]  Gathering local state\n")
    for root, _, files in os.walk(local_path):
        for filename in files:
            # Combine root and file to get the full path
            # Variable is named local_pth to avoid shadowing the local_path variable.
            # and because python is weird, so it would actually overwrite the local_path variable,
            # even though it's in a different scope.
            local_pth = os.path.join(root, filename)
            rel_pth = local_pth.replace(local_path + "/", "", 1)

            # Check if lock is present, and the file is still present on the remote
            if rel_pth in lock_content and rel_pth in paths:
                paths[rel_pth]["local_etag"] = lock_content[rel_pth]
    print(f"[FS]     Done gathering local state")

    print(f"\n\n[STAGE]  Updating files\n")
    for relative_path, info in paths.items():
        # Combine local path and relative path to get the full path
        local_file_path = os.path.join(local_path, relative_path)
        print(f"[FS]     Checking {relative_path}")

        # If (file doesn't exist locally) or (local etag/version is different from remote etag/version)
        if info["local_etag"] == None or info["local_etag"] != info["remote_etag"]:
            if info["local_etag"] != None:
                print(f"[FS]     Local etag:  {info['local_etag']}")
            print(f"[FS]     Remote etag: {info['remote_etag']}")
            print(f"[WEBDAV] Syncing {relative_path}")

            # Create containing directory if it doesn't exist
            if not os.path.isdir(
                (local_dir := os.path.dirname(os.path.abspath(local_file_path)))
            ):
                print(f"[FS]     Creating directory {os.path.dirname(local_file_path)}")
                os.makedirs(local_dir)

            webdav_client.download_sync(
                info["remote_path"],
                local_file_path,
            )
            print(f"[WEBDAV] Synced {local_file_path}")

        else:
            # If files does exist locally and and local etag/version is the same as remote etag/version, i.e.
            # the file content is the same, then the file is up to date.
            print(f"[WEBDAV] File {relative_path} is up to date")

        # New line for better readability
        print("")
    print(f"[FS]     File revisions now up to date with remote")

    print(f"\n\n[STAGE]  Deleting files\n")
    for root, _, files in os.walk(local_path):
        for filename in files:
            local_file_path = os.path.join(root, filename)
            rel_pth = local_file_path.replace(local_path + "/", "", 1)

            if (
                # If the file is not present on the remote
                rel_pth not in paths
                # If the lock file is present and we have a different file with the same name
                and os.path.exists(lock_file)
                and not os.path.samefile(local_file_path, lock_file)
            ):
                print(f"[FS]     Deleting {rel_pth}")
                os.remove(local_file_path)
    print(f"[FS]     Files now in sync with remote")

    print(f"\n\n[STAGE]  Deleting empty directories\n")
    for root, _, _ in os.walk(local_path):
        # If the directory is empty
        if len(os.listdir(root)) == 0:
            print(f"[FS]     Deleting empty directory {root}")
            os.rmdir(root)
    print(f"[FS]     Empty directories now deleted")

    print(f"\n\n[STAGE]  Writing lock file\n")
    with open(lock_file, "w") as f:
        # Write the etags to the lock file, converting the dictionary 'paths' to a flat dictionary
        json.dump(
            {k: v["remote_etag"] for k, v in paths.items()},
            f,
        )

    print("[APP]   Done!")


if __name__ == "__main__":
    # Run app if run directly
    app()
