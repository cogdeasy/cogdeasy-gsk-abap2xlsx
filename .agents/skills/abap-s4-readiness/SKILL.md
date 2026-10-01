---
name: abap-s4-readiness
description: Run the S/4HANA custom-code readiness inventory on this abapGit repo, read the findings, and write a Z-code brief from docs/zcode/TEMPLATE.md. Use for S/4HANA migration, clean-core or custom-code readiness tickets. Analysis only.
---

# ABAP S/4HANA readiness

## Boundary

Analysis only. Read the ABAP as source; never connect to or run anything on an SAP system. No
Basis work, no data migration, no system conversion. Devin analyses and drafts remediation; GSK's
SAP team decides and executes. Say "found by reading" and "designed, to run on a GSK system".
Never claim ATC or SAP-system results. Leave reviewer, decision, signature and date fields empty.

## Run the inventory

```bash
python3 tools/s4_inventory.py           # writes docs/s4/readiness-inventory.md
python3 tools/s4_inventory.py --check   # exit 1 if the committed file is stale
python3 tools/s4_inventory.py --out -   # print only
```

Stdlib Python, deterministic output. Rerun and commit the output after any change under `src/`.

Optional cross-check against the ABAP Cloud API (warnings, not a gate):

```bash
npm install && npx abaplint abaplint-steampunk.json
```

## Read the results

- **Findings summary**: occurrences and object counts per pattern id.
- **Findings by object**: which objects to pick up; one row per object.
- **Detail sections**: `file:line` per function module, table, class or statement.
- `fm` is "not on the allow-list", not "confirmed unreleased". `RELEASED_FMS` in the script is
  empty; confirm in SAP's Cloudification Repository before adding entries.
- Line numbers point at the start of the statement. Open the file and read the whole method
  before rating it.
- Map each finding to a wave from `docs/s4/remediation-plan.md`: 1 syntax, 2 non-released API
  (obvious successor or "needs SAP team decision"), 3 GUI/ALV/OLE.

## Write a Z-code brief

1. Copy `docs/zcode/TEMPLATE.md` to `docs/zcode/<object>.md` (lower case object name).
2. Fill `lines read` from the inventory's lines column after reading the whole object.
3. Dependency map: list every inventory finding for the object plus the custom classes it uses.
   State FI/CO, MM, SD tables touched, or "none".
4. S/4 risk: simplification items (tables or functions changed in S/4) and clean core (name each
   non-released API). Quote the wave and the proposed successor or "needs SAP team decision".
5. Defects found by reading, each with `file:line`; one ABAP Unit design per defect.
6. Recommended next step: fix PR (wave 1 or obvious wave 2), decision request, or retire.

## Before opening a PR

```bash
npm run lint                            # must report 0 issues
npm test                                # transpiled unit tests
python3 tools/s4_inventory.py --check
```
