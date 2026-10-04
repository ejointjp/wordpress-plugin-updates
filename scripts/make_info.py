#!/usr/bin/env python3
"""プラグインのメインファイルのヘッダーとreadme.txtから、更新情報（info.json）を作る。

使い方:
    make_info.py --main <slug>.php --slug <slug> --version <版> --package <zipのURL> \
        [--readme readme.txt] [--last-updated "YYYY-MM-DD HH:MM:SS"] > info.json

渡された版が、メインファイルのVersionやreadme.txtのStable tagと違えば、何も出さずに失敗する。
readme.txtから使うのは、ヘッダーのTested up toと、DescriptionとChangelogの節だけ。
標準ライブラリだけで動く。
"""

import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

# WordPressがヘッダーとして読む範囲（get_file_data()の8KB）に合わせる
HEADER_BYTES = 8192


def read_header(text, field):
    """プラグインのヘッダーの値を返す。なければ空文字。"""
    match = re.search(
        r"^[ \t/*#@]*" + re.escape(field) + r":(.*)$",
        text[:HEADER_BYTES],
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        return ""
    return re.sub(r"\s*(?:\*/|\?>).*", "", match.group(1)).strip()


def split_readme(text):
    """readme.txtを、先頭のヘッダー部分と「== 節 ==」ごとの本文に分ける。節の名前は小文字にする。"""
    head = []
    sections = {}
    current = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = re.match(r"^==\s*(.+?)\s*==\s*$", line)
        if match and not line.startswith("==="):
            current = match.group(1).lower()
            sections[current] = []
        elif current is None:
            head.append(line)
        else:
            sections[current].append(line)
    return "\n".join(head), {name: "\n".join(lines) for name, lines in sections.items()}


def read_readme_field(head, field):
    """readme.txtのヘッダー部分の値を返す。なければ空文字。"""
    match = re.search(r"^" + re.escape(field) + r":[ \t]*(.*)$", head, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def inline(text):
    """1行の中の記法（`code`、**太字**、[文字](URL)）をHTMLにする。記法以外はHTMLエスケープする。"""
    out = []
    for index, part in enumerate(re.split(r"`([^`]+)`", text)):
        escaped = html.escape(part, quote=True)
        if index % 2 == 1:
            out.append("<code>" + escaped + "</code>")
            continue
        escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', escaped)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        out.append(escaped)
    return "".join(out)


def to_html(body):
    """節の本文をHTMLにする。扱う記法は「= 見出し =」、「* 」の箇条書き、空行で区切った段落だけ。"""
    blocks = []
    paragraph = []
    items = []

    def flush():
        if paragraph:
            blocks.append("<p>" + "\n".join(inline(line) for line in paragraph) + "</p>")
            paragraph.clear()
        if items:
            blocks.append("<ul>" + "".join("<li>" + inline(item) + "</li>" for item in items) + "</ul>")
            items.clear()

    for raw in body.split("\n"):
        line = raw.strip()
        heading = re.match(r"^=\s*(.+?)\s*=$", line)
        if not line:
            flush()
        elif heading:
            flush()
            blocks.append("<h4>" + inline(heading.group(1)) + "</h4>")
        elif re.match(r"^[*-]\s+", line):
            if paragraph:
                flush()
            items.append(re.sub(r"^[*-]\s+", "", line))
        elif items:
            # 箇条書きの項目が次の行に続いている
            items[-1] += " " + line
        else:
            paragraph.append(line)
    flush()
    return "\n".join(blocks)


def build_info(main_text, readme_text, slug, version, package, last_updated):
    """info.jsonの中身を作る。版が食い違っていればSystemExitで止める。"""
    name = read_header(main_text, "Plugin Name")
    if not name:
        raise SystemExit("メインファイルにPlugin Nameがない")
    header_version = read_header(main_text, "Version")
    if header_version != version:
        raise SystemExit(f"メインファイルのVersion（{header_version}）が、リリースする版（{version}）と違う")

    info = {
        "name": name,
        "slug": slug,
        "version": version,
        "requires": read_header(main_text, "Requires at least"),
        "requires_php": read_header(main_text, "Requires PHP"),
        "tested": "",
        "author": read_header(main_text, "Author"),
        "last_updated": last_updated,
        "package": package,
        "sections": {},
    }

    if readme_text is not None:
        head, sections = split_readme(readme_text)
        stable = read_readme_field(head, "Stable tag")
        if stable != version:
            raise SystemExit(f"readme.txtのStable tag（{stable}）が、リリースする版（{version}）と違う")
        info["tested"] = read_readme_field(head, "Tested up to")
        for key in ("description", "changelog"):
            if sections.get(key, "").strip():
                info["sections"][key] = to_html(sections[key])

    if "description" not in info["sections"]:
        info["sections"]["description"] = "<p>" + html.escape(read_header(main_text, "Description"), quote=True) + "</p>"

    # 値のない項目（readme.txtがないときのtestedなど）は入れない
    return {key: value for key, value in info.items() if value != ""}


def main(argv=None):
    parser = argparse.ArgumentParser(description="プラグインの更新情報（info.json）を標準出力に書く")
    parser.add_argument("--main", required=True, help="プラグインのメインファイル（<slug>.php）")
    parser.add_argument("--readme", help="readme.txt（なければ省く）")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--version", required=True, help="リリースする版（タグからvを外したもの）")
    parser.add_argument("--package", required=True, help="zipのURL")
    parser.add_argument("--last-updated", help="UTCの日時（Y-m-d H:M:S）。省くと現在の時刻")
    args = parser.parse_args(argv)

    main_text = Path(args.main).read_text(encoding="utf-8")
    readme_text = Path(args.readme).read_text(encoding="utf-8") if args.readme else None
    last_updated = args.last_updated or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    info = build_info(main_text, readme_text, args.slug, args.version, args.package, last_updated)
    json.dump(info, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
