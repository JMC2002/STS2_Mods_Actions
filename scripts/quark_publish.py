#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://drive-pc.quark.cn/1/clouddrive"


class QuarkError(RuntimeError):
    pass


class QuarkClient:
    def __init__(self, cookie):
        self.cookie = cookie

    def request(self, method, path, params=None, payload=None):
        query = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "__t": str(int(time.time() * 1000)),
            "__dt": "1000",
        }
        if params:
            query.update(params)

        url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}?{urllib.parse.urlencode(query)}"
        data = None
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "cookie": self.cookie,
            "origin": "https://pan.quark.cn",
            "referer": "https://pan.quark.cn/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        }

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise QuarkError(f"HTTP {exc.code} from {path}: {body}") from exc

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QuarkError(f"Invalid JSON from {path}: {raw[:500]}") from exc

        status = result.get("status")
        if status not in (True, 200):
            message = result.get("message") or result.get("code") or result
            raise QuarkError(f"Quark API failed at {path}: {message}")

        return result

    def list_files(self, folder_id):
        files = []
        page = 1
        size = 100
        total = None

        while True:
            result = self.request(
                "GET",
                "file/sort",
                params={
                    "pdir_fid": folder_id,
                    "_page": str(page),
                    "_size": str(size),
                    "_sort": "file_type:asc,file_name:asc",
                    "_fetch_total": "1",
                },
            )
            data = result.get("data") or {}
            metadata = result.get("metadata") or {}
            chunk = data.get("list") or []
            files.extend(chunk)
            total = metadata.get("_total", total)

            if len(chunk) < size:
                break
            if total is not None and len(files) >= int(total):
                break
            page += 1

        return files

    def create_folder(self, parent_id, name):
        result = self.request(
            "POST",
            "file",
            payload={
                "pdir_fid": parent_id,
                "file_name": name,
                "dir_init_lock": False,
                "dir_path": "",
            },
        )
        fid = (result.get("data") or {}).get("fid")
        if not fid:
            raise QuarkError(f"Create folder returned no fid for {name}")
        return fid

    def move_files(self, file_ids, target_folder_id):
        if not file_ids:
            return

        result = self.request(
            "POST",
            "file/move",
            payload={
                "action_type": 1,
                "to_pdir_fid": target_folder_id,
                "filelist": file_ids,
                "exclude_fids": [],
            },
        )
        data = result.get("data") or {}
        task_id = data.get("task_id")
        if data.get("finish") or not task_id:
            return

        for retry in range(30):
            task = self.request(
                "GET",
                "task",
                params={"task_id": task_id, "retry_index": str(retry)},
            )
            task_data = task.get("data") or {}
            status = task_data.get("status")
            if status == 2:
                return
            if status == 3:
                raise QuarkError(f"Move task failed: {task_data.get('message', 'unknown')}")
            time.sleep(0.5)

        raise QuarkError(f"Move task did not finish: {task_id}")


def bool_arg(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def write_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def load_cookie(path):
    cookie = Path(path).read_text(encoding="utf-8").strip()
    if not cookie:
        raise QuarkError("Cookie file is empty.")
    return cookie


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    folder_id = (config.get("folderId") or "").strip()
    if not folder_id:
        raise QuarkError(f"folderId is required in {path}")
    return config


def get_history_folder_id(client, config, target_items, target_folder_id, dry_run):
    history_id = (config.get("historyFolderId") or "").strip()
    history_name = (config.get("historyFolderName") or "history").strip()
    if history_id:
        return history_id

    for item in target_items:
        if item.get("file_name") == history_name and item.get("dir"):
            return item.get("fid")

    if dry_run:
        return ""

    return client.create_folder(target_folder_id, history_name)


def preflight(args):
    config = load_config(args.config)
    client = QuarkClient(load_cookie(args.cookie_file))
    target_folder_id = config["folderId"].strip()
    target_items = client.list_files(target_folder_id)
    history_id = get_history_folder_id(client, config, target_items, target_folder_id, args.dry_run)

    if args.move_existing:
        old_zip_items = [
            item
            for item in target_items
            if item.get("file")
            and str(item.get("file_name", "")).lower().endswith(".zip")
        ]
    else:
        old_zip_items = []

    old_zip_ids = [item["fid"] for item in old_zip_items if item.get("fid")]
    if old_zip_ids and not history_id:
        raise QuarkError("Existing zip files found, but no history folder id is available.")

    print(f"Quark target folder: {target_folder_id}")
    print(f"Quark history folder: {history_id or '(not configured)'}")
    print(f"Existing zip files to archive: {len(old_zip_ids)}")
    for item in old_zip_items:
        print(f"  - {item.get('file_name')} ({item.get('fid')})")

    if old_zip_ids and not args.dry_run:
        client.move_files(old_zip_ids, history_id)
        print(f"Archived {len(old_zip_ids)} existing zip file(s).")
    elif old_zip_ids:
        print("Dry run enabled; existing zip files were not moved.")

    write_output("folder_id", target_folder_id)
    write_output("history_folder_id", history_id)
    write_output("archived_count", str(len(old_zip_ids)))


def verify(args):
    config = load_config(args.config)
    client = QuarkClient(load_cookie(args.cookie_file))
    zip_name = Path(args.zip_file).name
    target_items = client.list_files(config["folderId"].strip())
    uploaded = [
        item
        for item in target_items
        if item.get("file") and item.get("file_name") == zip_name
    ]
    if not uploaded:
        raise QuarkError(f"Uploaded file was not found in target folder: {zip_name}")

    latest = uploaded[0]
    print(f"Verified Quark upload: {zip_name} ({latest.get('fid')})")
    write_output("uploaded_file_id", latest.get("fid", ""))


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subcommands.add_parser("preflight")
    preflight_parser.add_argument("--cookie-file", required=True)
    preflight_parser.add_argument("--config", required=True)
    preflight_parser.add_argument("--zip-file", required=True)
    preflight_parser.add_argument("--move-existing", type=bool_arg, default=True)
    preflight_parser.add_argument("--dry-run", action="store_true")
    preflight_parser.set_defaults(func=preflight)

    verify_parser = subcommands.add_parser("verify")
    verify_parser.add_argument("--cookie-file", required=True)
    verify_parser.add_argument("--config", required=True)
    verify_parser.add_argument("--zip-file", required=True)
    verify_parser.set_defaults(func=verify)

    args = parser.parse_args()
    try:
        args.func(args)
    except QuarkError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
