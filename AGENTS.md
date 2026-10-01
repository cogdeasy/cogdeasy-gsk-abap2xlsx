# Working in this repository

GSK demo fork of [abap2xlsx](https://github.com/abap2xlsx/abap2xlsx), used as a stand-in for
GSK's ECC custom code ("Z-code"). The ABAP here is the **subject matter**: it is read as source
and linted, never executed against an SAP system from this repository.

## Scope

Devin does:

- read Z-programs and their dependencies as source code;
- document them in `docs/zcode/<object>.md` using `docs/zcode/TEMPLATE.md`;
- rate S/4HANA risk (simplification items, clean-core / released-API use);
- find defects by reading and design ABAP Unit tests (given / when / expect) for each;
- open fix PRs that go through CI and human review like any other change.

Devin does not do Basis work, click-configuration, data migration or the S/4HANA conversion
itself. Do not claim a defect is confirmed or a test passes on an SAP system: say "found by
reading" and "designed, to run on a GSK system".

## Toolchain

```bash
npm install     # @abaplint/cli and the transpiler
npm run lint    # abaplint, config in abaplint.json (syntax v702), must report 0 issues
npm test        # transpiled unit tests (upstream suite)
```

## How to work a Z-code ticket

1. Read the target object fully and record its line count.
2. Map dependencies: custom objects (`ZCL_*`, `ZIF_*`, `ZCX_*`, forms), function modules,
   SAP classes, DDIC tables. Say explicitly which FI/CO, MM or SD tables are touched, or none.
3. Rate S/4 risk on two axes: simplification items (low/medium/high) and clean core
   (low/medium/high, with the unreleased APIs named).
4. List defects found by reading, each with file:line, impact and the triggering input.
5. Design one ABAP Unit test per defect plus regression cases. Use the
   `<object>.testclasses.abap` naming convention for any test class you write.
6. Commit the brief to `docs/zcode/` and open a PR. `npm run lint` must stay at 0 issues.

## Conventions

- Do not tidy upstream ABAP opportunistically; change it only when the ticket is to fix it.
- Follow the upstream style enforced by abaplint: upper-case keywords (`keyword_case`) and
  `lo_`/`lv_`/`lt_` prefixes for local variables, as in the existing code.
- Conventional commit subjects (`docs:`, `fix:`, `test:`).
