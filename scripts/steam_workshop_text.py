#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


def bool_arg(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def read_text(path):
    if not path:
        return ""

    file_path = Path(path)
    if not file_path.is_file():
        return ""

    return file_path.read_text(encoding="utf-8").strip()


def write_text(path, content):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def warn(message):
    print(f"::warning::{message}", file=sys.stderr)


def extract_changelog_section(path, version):
    content = read_text(path)
    if not content:
        return ""

    escaped = re.escape(version)
    target_header = re.compile(rf"^\s*##\s+(?:\[?v?{escaped}\]?)(?:\s|$)", re.IGNORECASE)
    any_version_header = re.compile(r"^\s*##\s+(?:\[?v?\d+(?:\.\d+)+\]?)(?:\s|$)", re.IGNORECASE)
    lines = content.splitlines()
    recording = False
    extracted = []

    for line in lines:
        if recording and any_version_header.match(line):
            break

        if recording:
            extracted.append(line)
            continue

        if target_header.match(line):
            recording = True

    return "\n".join(extracted).strip()


def convert_inline(text):
    placeholders = {}

    def stash(match):
        key = f"\0CODE{len(placeholders)}\0"
        placeholders[key] = f"[code]{match.group(1)}[/code]"
        return key

    text = re.sub(r"`([^`]+)`", stash, text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[url=\2]\1[/url]", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"[b]\1[/b]", text)
    text = re.sub(r"__([^_]+)__", r"[b]\1[/b]", text)
    text = re.sub(r"~~([^~]+)~~", r"[strike]\1[/strike]", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"[i]\1[/i]", text)

    for key, value in placeholders.items():
        text = text.replace(key, value)

    return text


def close_list(output, list_state):
    if list_state == "ul":
        output.append("[/list]")
    elif list_state == "ol":
        output.append("[/olist]")
    return None


def markdown_to_bbcode(markdown):
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output = []
    list_state = None
    in_code_block = False
    code_lines = []
    quote_lines = []

    def flush_quote():
        nonlocal quote_lines
        if quote_lines:
            output.append("[quote]")
            output.extend(convert_inline(line) for line in quote_lines)
            output.append("[/quote]")
            quote_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            flush_quote()
            list_state = close_list(output, list_state)
            if in_code_block:
                output.append("[code]")
                output.extend(code_lines)
                output.append("[/code]")
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_quote()
            list_state = close_list(output, list_state)
            if output and output[-1] != "":
                output.append("")
            continue

        quote_match = re.match(r"^\s*>\s?(.*)$", line)
        if quote_match:
            quote_lines.append(quote_match.group(1))
            continue

        flush_quote()

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            list_state = close_list(output, list_state)
            level = min(len(heading_match.group(1)), 3)
            output.append(f"[h{level}]{convert_inline(heading_match.group(2).strip())}[/h{level}]")
            continue

        unordered_match = re.match(r"^\s*[-+*]\s+(.+)$", line)
        if unordered_match:
            if list_state != "ul":
                list_state = close_list(output, list_state)
                output.append("[list]")
                list_state = "ul"
            output.append(f"[*]{convert_inline(unordered_match.group(1).strip())}")
            continue

        ordered_match = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ordered_match:
            if list_state != "ol":
                list_state = close_list(output, list_state)
                output.append("[olist]")
                list_state = "ol"
            output.append(f"[*]{convert_inline(ordered_match.group(1).strip())}")
            continue

        list_state = close_list(output, list_state)
        output.append(convert_inline(line))

    if in_code_block:
        output.append("[code]")
        output.extend(code_lines)
        output.append("[/code]")

    flush_quote()
    close_list(output, list_state)
    return "\n".join(output).strip()


def maybe_convert(text, enabled):
    if not text:
        return ""
    return markdown_to_bbcode(text) if enabled else text.strip()


def build_change_note(args):
    if args.change_note.strip():
        return maybe_convert(args.change_note, args.markdown_to_bbcode)

    zh_section = maybe_convert(extract_changelog_section(args.changelog_zh, args.version), args.markdown_to_bbcode)
    en_section = maybe_convert(extract_changelog_section(args.changelog_en, args.version), args.markdown_to_bbcode)

    sections = []
    if zh_section:
        sections.append("[h2]\u7b80\u4f53\u4e2d\u6587 / \u7e41\u9ad4\u4e2d\u6587[/h2]\n" + zh_section)
    if en_section:
        sections.append("[h2]English[/h2]\n" + en_section)

    if sections:
        return "\n\n".join(sections).strip()

    return f"Release v{args.version}"


def collect_changelog_warnings(args):
    if args.change_note.strip():
        return []

    warnings = []
    for label, path in (
        ("Chinese", args.changelog_zh),
        ("English", args.changelog_en),
    ):
        if not path:
            continue

        changelog_path = Path(path)
        if not changelog_path.is_file():
            warnings.append(f"{label} changelog not found at '{path}'. This language will be omitted from the change note.")
            continue

        if not extract_changelog_section(path, args.version):
            warnings.append(f"{label} changelog has no section for version '{args.version}'. This language will be omitted from the change note.")

    return warnings


def resolve_description_source(workspace, requested_path, fallback_name):
    if requested_path:
        requested = Path(requested_path)
        if requested.is_file():
            return requested

    fallback = workspace / fallback_name
    if fallback.is_file():
        return fallback

    return None


def prepare(args):
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        raise SystemExit(f"Workshop workspace not found: {workspace}")

    workshop_json_path = workspace / "workshop.json"
    if not workshop_json_path.is_file():
        raise SystemExit(f"workshop.json not found: {workshop_json_path}")

    change_note = build_change_note(args)
    warnings = collect_changelog_warnings(args)
    workshop_json = json.loads(workshop_json_path.read_text(encoding="utf-8"))
    workshop_json["changeNote"] = change_note
    workshop_json_path.write_text(
        json.dumps(workshop_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    description_outputs = {}
    missing_descriptions = []
    description_sources = {
        "Chinese": ("workshop_zh.txt", resolve_description_source(workspace, args.description_zh, "workshop_zh.txt")),
        "English": ("workshop_en.txt", resolve_description_source(workspace, args.description_en, "workshop_en.txt")),
    }

    for label, (output_name, source_path) in description_sources.items():
        if source_path is None:
            missing_descriptions.append(label)
            warnings.append(f"{label} Workshop description not found. No localized description file will be generated for this language.")
            continue
        converted = maybe_convert(read_text(source_path), args.markdown_to_bbcode)
        output_path = workspace / output_name
        write_text(output_path, converted)
        description_outputs[output_name] = str(output_path)

    for message in warnings:
        warn(message)

    result = {
        "change_note": change_note,
        "description_outputs": description_outputs,
        "missing_descriptions": missing_descriptions,
        "warnings": warnings,
    }
    result_json = json.dumps(result, ensure_ascii=False)
    if args.result_json:
        write_text(args.result_json, result_json)
    else:
        print(result_json)


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subcommands.add_parser("prepare")
    prepare_parser.add_argument("--workspace", required=True)
    prepare_parser.add_argument("--version", required=True)
    prepare_parser.add_argument("--changelog-zh", default="CHANGELOG.md")
    prepare_parser.add_argument("--changelog-en", default="CHANGELOG_en.md")
    prepare_parser.add_argument("--description-zh", default="workshop_zh.txt")
    prepare_parser.add_argument("--description-en", default="workshop_en.txt")
    prepare_parser.add_argument("--change-note", default="")
    prepare_parser.add_argument("--markdown-to-bbcode", type=bool_arg, default=True)
    prepare_parser.add_argument("--result-json", default="")
    prepare_parser.set_defaults(func=prepare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
