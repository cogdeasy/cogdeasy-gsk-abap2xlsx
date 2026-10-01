#!/usr/bin/env python3
"""S/4HANA custom-code readiness inventory for an abapGit source tree.

Walks src/, counts objects by type and lines, and flags patterns relevant to S/4HANA and
clean core. Output is Markdown and deterministic (sorted, no timestamps).

    python3 tools/s4_inventory.py                    # writes docs/s4/readiness-inventory.md
    python3 tools/s4_inventory.py --check            # exit 1 if the committed file is stale
    python3 tools/s4_inventory.py --out -            # print to stdout

Analysis only: this reads source text. It does not connect to an SAP system, and its
classifications are heuristics to be confirmed by GSK's SAP team.
"""

import argparse
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TYPE_LABELS = {
    "clas": "class",
    "intf": "interface",
    "prog": "program",
    "fugr": "function group",
    "xslt": "transformation (XSLT/ST)",
    "msag": "message class",
    "devc": "package",
    "doma": "DDIC domain",
    "dtel": "DDIC data element",
    "tabl": "DDIC table/structure",
    "ttyp": "DDIC table type",
    "view": "DDIC view",
    "ddls": "CDS view",
    "enqu": "lock object",
    "shlp": "search help",
}
DDIC_TYPES = {"doma", "dtel", "tabl", "ttyp", "view", "ddls", "enqu", "shlp"}

# Function modules known to be released for ABAP Cloud / clean core. Left empty on purpose:
# check each FM in SAP's Cloudification Repository (github.com/SAP/abap-atc-cr-cv-s4hc)
# and add it here only once confirmed.
RELEASED_FMS = frozenset()

LIST_OUTPUT = ("WRITE", "ULINE", "SKIP", "NEW-PAGE", "NEW-LINE", "FORMAT", "TOP-OF-PAGE",
               "END-OF-PAGE", "AT LINE-SELECTION", "AT USER-COMMAND")

# Obsolete statements (ABAP keyword documentation, "Obsolete Language Elements").
OBSOLETE = [
    ("MOVE", re.compile(r"^MOVE\s(?!.*\?TO)")),
    ("COMPUTE", re.compile(r"^COMPUTE\s")),
    ("ADD", re.compile(r"^ADD\s")),
    ("SUBTRACT", re.compile(r"^SUBTRACT\s")),
    ("MULTIPLY", re.compile(r"^MULTIPLY\s")),
    ("DIVIDE", re.compile(r"^DIVIDE\s")),
    ("REFRESH", re.compile(r"^REFRESH\s")),
    ("RANGES", re.compile(r"^RANGES\s")),
    ("TABLES", re.compile(r"^TABLES\s")),
    ("TYPE-POOLS", re.compile(r"^TYPE-POOLS\s")),
    ("FORM", re.compile(r"^FORM\s")),
    ("PERFORM", re.compile(r"^PERFORM\s")),
    ("SEARCH", re.compile(r"^SEARCH\s")),
    ("LOCAL", re.compile(r"^LOCAL\s")),
    ("ON CHANGE OF", re.compile(r"^ON\s+CHANGE\s+OF\s")),
    ("CATCH SYSTEM-EXCEPTIONS", re.compile(r"^CATCH\s+SYSTEM-EXCEPTIONS\b")),
    ("CLIENT SPECIFIED", re.compile(r"\bCLIENT\s+SPECIFIED\b")),
]

CATEGORIES = [
    ("fm", "CALL FUNCTION to non-released SAP function modules"),
    ("fm_dynamic", "CALL FUNCTION with a dynamic name"),
    ("select", "Direct SELECT on SAP standard tables"),
    ("occurs", "OCCURS / WITH HEADER LINE"),
    ("transformation", "CALL TRANSFORMATION"),
    ("gui", "cl_gui_* references (SAP GUI dependency)"),
    ("list", "Classic list output (WRITE, ULINE, SKIP, ...)"),
    ("write_to", "WRITE ... TO (formatting into a variable)"),
    ("obsolete", "Obsolete statements"),
]


def is_custom(name):
    return name[:1] in ("Z", "Y")


def scan_template(line, i):
    """Return the index of the closing '|' of a string template starting at line[i]."""
    j, n = i + 1, len(line)
    while j < n:
        ch = line[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "|":
            return j
        if ch == "{":
            j = scan_expr(line, j + 1)
        j += 1
    return n - 1


def scan_expr(line, j):
    """Return the index of the '}' closing an embedded expression that starts at line[j]."""
    n, depth = len(line), 0
    while j < n:
        ch = line[j]
        if ch in "'`":
            j = scan_quote(line, j)
        elif ch == "|":
            j = scan_template(line, j)
        elif ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0:
                return j
            depth -= 1
        j += 1
    return n - 1


def scan_quote(line, i):
    """Return the index of the closing quote of a '...' or `...` literal."""
    q, j, n = line[i], i + 1, len(line)
    while j < n:
        if line[j] == q:
            if j + 1 < n and line[j + 1] == q:
                j += 2
                continue
            return j
        j += 1
    return n - 1


def mask_quote(seg):
    """Blank the contents of a '...' or `...` literal, keeping the delimiters."""
    return seg[0] + "_" * max(len(seg) - 2, 0) + (seg[-1] if len(seg) > 1 else "")


def mask_template(seg):
    """Blank the literal text of a |...| template but keep code inside { } expressions."""
    out, k, n = ["|"], 1, len(seg)
    end = n - 1 if n > 1 and seg[-1] == "|" else n
    while k < end:
        ch = seg[k]
        if ch == "\\":
            out.append("_" * len(seg[k:k + 2]))
            k += 2
            continue
        if ch == "{":
            close = min(scan_expr(seg, k + 1), end - 1)
            out.append("{")
            out.append(mask_code(seg[k + 1:close]))
            out.append(seg[close] if close > k else "")
            k = close + 1
            continue
        out.append("_")
        k += 1
    if end < n:
        out.append("|")
    return "".join(out)


def mask_code(text):
    """Blank literals inside an embedded expression, keeping its code."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "'`|":
            j = min(scan_template(text, i) if ch == "|" else scan_quote(text, i), n - 1)
            seg = text[i:j + 1]
            out.append(mask_template(seg) if ch == "|" else mask_quote(seg))
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def statements(text):
    """Yield (line, raw, code) per ABAP statement, with chains expanded.

    raw keeps literals; code has comments removed and literal contents blanked to '_'
    (code inside string-template { } is kept), so both strings line up by position.
    """
    raw, code, lines = [], [], []
    for ln, line in enumerate(text.splitlines(), 1):
        if line.startswith("*"):
            continue
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if ch == '"':
                break
            if ch in "'`|":
                j = scan_template(line, i) if ch == "|" else scan_quote(line, i)
                seg = line[i:j + 1]
                raw.extend(seg)
                code.extend(mask_template(seg) if ch == "|" else mask_quote(seg))
                lines.extend([ln] * len(seg))
                i = j + 1
                continue
            if ch == ".":
                yield from split_chain("".join(raw), "".join(code), lines)
                raw, code, lines = [], [], []
            else:
                raw.append(ch)
                code.append(ch)
                lines.append(ln)
            i += 1
        raw.append(" ")
        code.append(" ")
        lines.append(ln)
    if "".join(code).strip():
        yield from split_chain("".join(raw), "".join(code), lines)


def split_chain(raw, code, lines):
    colon = code.find(":")
    if colon < 0:
        parts = [(0, len(code))]
        head = None
    else:
        head = (0, colon)
        parts, depth, start = [], 0, colon + 1
        for k in range(colon + 1, len(code)):
            ch = code[k]
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append((start, k))
                start = k + 1
        parts.append((start, len(code)))
    for a, b in parts:
        body_code, body_raw = code[a:b], raw[a:b]
        if not body_code.strip():
            continue
        offset = a + len(body_code) - len(body_code.lstrip())
        first = lines[offset] if offset < len(lines) else lines[-1]
        if head:
            h_code = code[head[0]:head[1]].strip()
            h_raw = raw[head[0]:head[1]].strip()
            yield first, (h_raw + " " + body_raw.strip()), (h_code + " " + body_code.strip())
        else:
            yield first, body_raw.strip(), body_code.strip()


def analyse_statement(stmt_code, stmt_raw):
    """Return a list of (category, detail) findings for one statement."""
    up = " ".join(stmt_code.upper().split())
    raw = " ".join(stmt_raw.split())
    found = []

    m = re.match(r"^CALL\s+FUNCTION\s+", up)
    if m:
        rest = raw[m.end():]
        lit = re.match(r"['`]([^'`]+)['`]", rest)
        if lit:
            fm = lit.group(1).upper()
            if not is_custom(fm) and fm not in RELEASED_FMS:
                found.append(("fm", fm))
        else:
            found.append(("fm_dynamic", rest.split(" ")[0]))

    if re.match(r"^(SELECT|OPEN\s+CURSOR|WITH\s+\+)\b", up):
        for t in re.finditer(r"\b(?:FROM|JOIN)\s+(?!@)\(?([A-Z0-9_/]+)", up):
            name = t.group(1)
            if not is_custom(name):
                found.append(("select", name))

    if re.search(r"\bOCCURS\b", up) or re.search(r"\bWITH\s+HEADER\s+LINE\b", up):
        found.append(("occurs", "OCCURS" if "OCCURS" in up else "WITH HEADER LINE"))

    if re.match(r"^CALL\s+TRANSFORMATION\s", up):
        found.append(("transformation", up.split()[2]))

    for g in sorted(set(re.findall(r"\bCL_GUI_[A-Z0-9_]+", up))):
        found.append(("gui", g))

    for kw in LIST_OUTPUT:
        if re.match(r"^" + kw.replace(" ", r"\s+") + r"(\s|:|$)", up):
            if kw == "WRITE" and re.search(r"\sTO\s", up):
                found.append(("write_to", "WRITE ... TO"))
            else:
                found.append(("list", kw))
            break

    for kw, rx in OBSOLETE:
        if rx.search(up):
            found.append(("obsolete", kw))
    return found


def split_name(fname):
    parts = fname.split(".")
    if len(parts) < 3:
        return None
    return parts[0].upper(), parts[1].lower()


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def code_line_count(text):
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if s and not line.startswith("*") and not s.startswith('"'):
            count += 1
    return count


def collect(src):
    objects = {}  # (package, name, type) -> dict
    packages = {}
    findings = []  # (category, detail, relpath, line, object key)
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, ROOT).replace(os.sep, "/") + "/"
        for fname in sorted(filenames):
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            if fname == "package.devc.xml":
                m = re.search(r"<CTEXT>(.*?)</CTEXT>", read(path))
                packages[rel_dir] = m.group(1) if m else ""
                continue
            parsed = split_name(fname)
            if not parsed:
                continue
            name, otype = parsed
            key = (rel_dir, name, otype)
            obj = objects.setdefault(key, {"lines": 0, "code": 0, "files": 0, "sub": ""})
            text = read(path)
            if fname.endswith(".xml") and otype == "tabl":
                m = re.search(r"<TABCLASS>(\w+)</TABCLASS>", text)
                obj["sub"] = m.group(1) if m else ""
            if fname.endswith(".abap"):
                obj["files"] += 1
                obj["lines"] += len(text.splitlines())
                obj["code"] += code_line_count(text)
                for line, stmt_raw, stmt_code in statements(text):
                    for cat, detail in analyse_statement(stmt_code, stmt_raw):
                        findings.append((cat, detail, rel, line, key))
            elif fname.endswith(".source.xml"):
                obj["files"] += 1
                obj["lines"] += len(text.splitlines())
    return objects, packages, findings


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def locations(items):
    by_file = defaultdict(list)
    for rel, line in items:
        by_file[rel].append(line)
    parts = []
    for rel in sorted(by_file):
        lines = sorted(set(by_file[rel]))
        parts.append("`%s`:%s" % (rel, ",".join(str(x) for x in lines)))
    return "<br>".join(parts)


def render(objects, packages, findings):
    out = [
        "# S/4HANA custom-code readiness inventory",
        "",
        "Generated by `python3 tools/s4_inventory.py` from `src/`. Do not edit by hand; rerun the",
        "script. Analysis only: read as source, not run in an SAP system. Pattern matches are",
        "heuristics for GSK's SAP team to confirm, not ATC results.",
        "",
        "## Objects by type",
        "",
    ]
    by_type = defaultdict(lambda: [0, 0, 0])
    for (pkg, name, otype), o in objects.items():
        label = TYPE_LABELS.get(otype, otype)
        if otype == "tabl":
            label = "DDIC transparent table" if o["sub"] == "TRANSP" else "DDIC structure"
        t = by_type[(otype in DDIC_TYPES, label, otype)]
        t[0] += 1
        t[1] += o["lines"]
        t[2] += o["code"]
    rows, tot = [], [0, 0, 0]
    for (ddic, label, otype) in sorted(by_type):
        c, l, k = by_type[(ddic, label, otype)]
        rows.append([label, otype.upper(), c, l if l else "-", k if k else "-"])
        tot = [tot[0] + c, tot[1] + l, tot[2] + k]
    rows.append(["**total**", "", tot[0], tot[1], tot[2]])
    out += md_table(["type", "abapGit", "objects", "source lines", "code lines"], rows)
    out += ["", "Source lines include comments and blank lines; code lines exclude both. XSLT lines",
            "are counted from `*.xslt.source.xml`.", "", "## Objects by package", ""]

    pkg_rows = []
    for pkg in sorted({k[0] for k in objects}):
        objs = [(k, o) for k, o in objects.items() if k[0] == pkg]
        code_objs = [x for x in objs if x[0][2] not in DDIC_TYPES]
        pkg_rows.append(["`%s`" % pkg, packages.get(pkg, ""), len(objs), len(code_objs),
                         sum(o["lines"] for _, o in objs)])
    out += md_table(["folder", "package description", "objects", "non-DDIC objects", "source lines"],
                    pkg_rows)

    counts = defaultdict(int)
    obj_counts = defaultdict(set)
    for cat, _, _, _, key in findings:
        counts[cat] += 1
        obj_counts[cat].add(key)
    out += ["", "## Findings summary", ""]
    out += md_table(["id", "pattern", "occurrences", "objects"],
                    [[cid, title, counts[cid], len(obj_counts[cid])] for cid, title in CATEGORIES])

    out += ["", "## Findings by object", "",
            "Objects with at least one finding. Columns are occurrence counts per pattern id.", ""]
    per_obj = defaultdict(lambda: defaultdict(int))
    for cat, _, _, _, key in findings:
        per_obj[key][cat] += 1
    rows = []
    for key in sorted(per_obj):
        pkg, name, otype = key
        rows.append(["`%s`" % name, otype.upper(), "`%s`" % pkg, objects[key]["lines"]]
                    + [per_obj[key].get(cid, "") for cid, _ in CATEGORIES])
    out += md_table(["object", "type", "folder", "lines"] + [c for c, _ in CATEGORIES], rows)

    details = [
        ("fm", "function module"),
        ("fm_dynamic", "name expression"),
        ("select", "table"),
        ("occurs", "form"),
        ("transformation", "transformation"),
        ("gui", "class"),
        ("list", "statement"),
        ("write_to", "statement"),
        ("obsolete", "statement"),
    ]
    for cid, col in details:
        title = dict(CATEGORIES)[cid]
        out += ["", "## %s: %s" % (cid, title), ""]
        grouped = defaultdict(list)
        for cat, detail, rel, line, _ in findings:
            if cat == cid:
                grouped[detail].append((rel, line))
        if not grouped:
            out.append("None found.")
            continue
        rows = [["`%s`" % d, len(grouped[d]), locations(grouped[d])]
                for d in sorted(grouped, key=lambda d: (-len(grouped[d]), d))]
        out += md_table([col, "count", "locations (file:line)"], rows)

    out += ["", "## Method", "",
            "- Objects are identified from abapGit file names (`name.type.*`); folders follow",
            "  `.abapgit.xml` PREFIX folder logic.",
            "- Statements are parsed after removing comments (`*` in column 1, `\"` to end of line)",
            "  and blanking literal and string-template contents; chained statements (`:`) are",
            "  expanded. Line numbers point at the start of each statement or chain element.",
            "- `fm`: every `CALL FUNCTION` to a non-Z/Y module not on the script's `RELEASED_FMS`",
            "  allow-list. The list is empty; confirm release status in SAP's Cloudification",
            "  Repository before relying on it.",
            "- `select`: table names after `FROM` / `JOIN` in `SELECT` statements that do not start",
            "  with Z or Y. Selects from internal tables (`FROM @itab`) are skipped.",
            "- `write_to` is reported apart from `list` because it formats into a variable rather",
            "  than writing a list; it is a syntax item, not a GUI item.",
            "- `obsolete`: " + ", ".join("`%s`" % k for k, _ in OBSOLETE) + ".",
            "- Test classes (`*.testclasses.abap`) are included and counted with their class.",
            ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=os.path.join(ROOT, "src"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "s4", "readiness-inventory.md"))
    ap.add_argument("--check", action="store_true", help="fail if --out differs from fresh output")
    args = ap.parse_args()

    text = render(*collect(os.path.abspath(args.src)))
    if args.out == "-":
        sys.stdout.write(text)
        return 0
    if args.check:
        current = read(args.out) if os.path.exists(args.out) else ""
        if current != text:
            print("%s is stale; run python3 tools/s4_inventory.py" % args.out, file=sys.stderr)
            return 1
        return 0
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
