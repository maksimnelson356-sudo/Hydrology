---
slug: rebuild-installer-qa
status: drafting
intent: clear
review_required: false
pending-action: write .omo/plans/rebuild-installer-qa.md
approach: >
  Rebuild full installer: (1) PyInstaller .exe, (2) Inno Setup Setup.exe.
  Then full QA: pytest + manual Excel→calculation stitching check.
  No source code fixes unless bugs found during QA.
---

# Draft: rebuild-installer-qa

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
<!-- id | outcome (one line) | status: active|deferred | evidence path -->

## Open assumptions (announced defaults)
<!-- Record any default you adopt instead of asking, so the user can veto it at the gate. -->
<!-- assumption | adopted default | rationale | reversible? -->

## Findings (cited - path:lines)
- build_installer.py:248 — defines build order (PyInstaller → Inno Setup)
- build.py:219 — PyInstaller build command with --hidden-import modules
- dist/ empty — no prior .exe built
- installer_output/ empty — no prior Setup.exe
- venv/ has pyinstaller.exe — depends available
- Inno Setup (ISCC.exe) not verified — may block stage 2
- test_*.py present (test_all_functions, test_edge_cases, test_q, test_real_data, test_sp_compliance)
- DataController._parse_work_sheets (gui/controller/data_controller.py:106-132) — sheet parser, potential mismatch source
- ShortWidget (gui/widget_short.py:244-326) — analog selection, potential data mismatch

## Decisions (with rationale)
- Rebuild full pipeline (both stages), don't skip Inno Setup unless unavailable
- Run pytest first; fix only bugs found; don't refactor
- Manual QA with test_data_clean.xlsx and unified template

## Scope IN
- PyInstaller build → .exe in dist/
- Inno Setup → Setup.exe in installer_output/
- pytest test suite execution
- Manual data stitching QA (Excel → calculations)
- Report found bugs/errors/stitching mismatches

## Scope OUT (Must NOT have)
- No feature changes, no refactoring
- No new dependencies
- Don't fix bugs not confirmed by QA

## Open questions
- Is Inno Setup installed? (need to verify iscc.exe)
- Which specific errors/bugs need fixing? (need pytest results)

## Approval gate
status: awaiting-approval
Next: run full plan (build + pytest + QA) after approval.
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
