#!/usr/bin/env python3
# coding: utf8
#
# Generate all-in-one Markdown file for ``doc-cn``
# Tip: 不支持中文文件名
# readme.md 中的目录引用的md多次（或者md的sub heading)，以第一次出现为主

from __future__ import print_function, unicode_literals

import re
import os
import sys
import json
import unicodedata

followups = []
in_toc = False
contents = []

hyper_link_pattern = re.compile(r"\[(.*?)\]\((.*?)(#.*?)?\)")
toc_line_pattern = re.compile(r"([\-\+]+)\s\[(.*?)\]\((.*?)(#.*?)?\)")
image_link_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
level_pattern = re.compile(r"(\s*[\-\+]+)\s")
# match all headings
heading_patthern = re.compile(r"(^#+|\n#+)\s")
# match copyable snippet code
copyable_snippet_pattern = re.compile(r"{{< copyable .* >}}")
custom_content_tidb = re.compile(
    r"""<CustomContent +platform=["']tidb["'] *>(.|\n)*?</CustomContent>\n"""
)
custom_content_tidb_cloud = re.compile(
    r"""<CustomContent +platform=["']tidb-cloud["'] *>(.|\n)*?</CustomContent>\n"""
)

sysArgvList = sys.argv

try:
    entry_file = sys.argv[1]
except IndexError:
    entry_file = "TOC.md"

# stage 1, parse toc
with open(entry_file) as fp:
    level = 0
    current_level = ""
    for line in fp:
        if not in_toc and not line.startswith("<!-- "):
            in_toc = True
        elif in_toc and not line.startswith("#") and line.strip():
            ## get level from space length
            level_space_str = level_pattern.findall(line)[0][:-1]
            level = len(level_space_str) // 2 + 1  ## python divide get integer

            matches = toc_line_pattern.findall(line)
            if matches:
                for match in matches:
                    fpath = match[2]
                    if fpath.endswith(".md"):
                        # remove the first slash in the relative path
                        fpath = fpath[1:]
                        key = ("FILE", level, fpath)
                        if key not in followups:
                            followups.append(key)
                    elif fpath.startswith("http"):
                        ## remove list format character `- `, `+ `
                        followups.append(("TOC", level, line.strip()[2:]))
            else:
                name = line.strip().split(None, 1)[-1]
                key = ("TOC", level, name)
                if key not in followups:
                    followups.append(key)

        else:
            pass

# stage 2, get file heading
file_link_name = {}
title_pattern = re.compile(r"(^#+)\s.*")
for tp, lv, f in followups:
    if tp != "FILE":
        continue
    try:
        for line in open(f).readlines():
            if line.startswith("#"):
                tag = line.strip()
                break
    except Exception as e:
        print(e)
        tag = ""
    if tag.startswith("# "):
        tag = tag[2:]
    elif tag.startswith("## "):
        tag = tag[3:]
    file_link_name[f] = tag.lower().replace(" ", "-")

def load_variables():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    variables_path = os.path.join(current_dir, "../variables.json")
    try:
        with open(variables_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}
variable_pattern = re.compile(r"{{{\s*\.(.+?)\s*}}}")

def get_value_by_path(obj, path):
    keys = path.split(".")
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        else:
            return ""
    return str(obj)

def replace_variables(text, variables):
    def replacer(match):
        path = match.group(1).strip()
        value = get_value_by_path(variables, path)
        return str(value) if value != "" else match.group(0)
    return variable_pattern.sub(replacer, text)

def slugify(title):
    slug = title.strip().lower()
    slug = unicodedata.normalize('NFKD', slug)
    slug = re.sub(r"[^\w\s-]", "", slug)  # remove punctuation
    slug = re.sub(r"[\s_]+", "-", slug)   # spaces and underscores to dash
    return slug

custom_id_map = {}  # key = custom-id, value = slugified title

heading_with_custom_id_pattern = re.compile(r"^(#+)\s+(.*?)(?:\s+\{#([^\}]+)\})?$", re.MULTILINE)

def extract_custom_ids_and_clean(chapter):
    def repl(match):
        hashes = match.group(1)
        title = match.group(2).strip()
        custom_id = match.group(3)

        if custom_id:
            anchor = slugify(title)
            custom_id_map[custom_id] = anchor
            return f"{hashes} {title}"  # remove the `{#...}`
        else:
            return match.group(0)

    return heading_with_custom_id_pattern.sub(repl, chapter)

def replace_custom_id_links(content):
    # [text](/path#custom-id) → [text](#anchor-text)
    def repl(match):
        text, url, frag = match.group(1), match.group(2), match.group(3)
        if frag and frag.startswith("#"):
            cid = frag[1:]
            if cid in custom_id_map:
                return f"[{text}](#{custom_id_map[cid]})"
        return match.group(0)

    return hyper_link_pattern.sub(repl, content)

def replace_link_wrap(chapter, name):

    # Note: 仅仅支持 hash 匹配，如果在多个文档中有同名 heading 会碰撞
    # 支持 chapter 文档中的 ./ddd.md, xxx.md, xxx.md#xxx 等
    def replace_link(match):
        full = match.group(0)
        link_name = match.group(1)
        link = match.group(2)
        frag = match.group(3)
        if link.startswith("http"):
            return full
        elif link.endswith(".md") or ".md#" in link:
            if not frag:
                link = link[1:]
                for fpath in file_link_name:
                    if link == fpath:
                        frag = "#" + file_link_name[fpath]
            return "[%s](%s)" % (link_name, frag)
        elif (
            link.endswith(".png")
            or link.endswith(".jpeg")
            or link.endswith(".svg")
            or link.endswith(".gif")
            or link.endswith(".jpg")
        ):
            # special handing for pic
            img_link = re.sub(r"[\.\/]*media\/", "./media/", link, count=0, flags=0)
            return "[%s](%s)" % (link_name, img_link)
        else:
            return full

    return hyper_link_pattern.sub(replace_link, chapter)


def replace_heading_func(diff_level=0):
    def replace_heading(match):
        if diff_level == 0:
            return match.group(0)
        else:
            return "\n" + "#" * (match.group(0).count("#") + diff_level) + " "

    return replace_heading


# remove copyable snippet code
def remove_copyable(match):
    return ""

variables = load_variables()

# stage 3, concat files
for type_, level, name in followups:
    if type_ == "TOC":
        contents.append("\n{} {}\n".format("#" * level, name))
    elif type_ == "RAW":
        contents.append(name)
    elif type_ == "FILE":
        try:
            with open(name) as fp:
                chapter = fp.read()
                chapter = replace_variables(chapter, variables)
                chapter = replace_link_wrap(chapter, name)
                chapter = copyable_snippet_pattern.sub(remove_copyable, chapter)
                chapter = extract_custom_ids_and_clean(chapter)
                chapter = replace_custom_id_links(chapter)
                # This block is to filter <CustomContent paltform="xxx"> xxx </CustomContent>
                try:
                    custom_content_platform = sys.argv[3]
                except IndexError:
                    custom_content_platform = "tidb"
                # print("platform: ", custom_content_platform)
                if custom_content_platform == "tidb":
                    # print("removing custom content: tidb-cloud")
                    # Cloud specified content should not render in tidb pdf
                    chapter = custom_content_tidb_cloud.sub(lambda x: "", chapter)
                elif custom_content_platform == "tidb-cloud":
                    # print("removing custom content: tidb")
                    # Tidb Specified content should not render in tidb-cloud pdf
                    chapter = custom_content_tidb.sub(lambda x: "", chapter)

                # fix heading level
                diff_level = level - heading_patthern.findall(chapter)[0].count("#")

                chapter = heading_patthern.sub(
                    replace_heading_func(diff_level), chapter
                )
                contents.append(chapter)
                contents.append("")  # add an empty line
        except Exception as e:
            print(e)
            print("generate file error: ignore!")

# stage 4, generage final doc.md
try:
    target_doc_file = sys.argv[2]
except IndexError:
    target_doc_file = "doc.md"
with open(target_doc_file, "w") as fp:
    fp.write("\n".join(contents))
