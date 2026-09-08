# rebuild-installer-qa - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->
**What you'll get:** Rebuilt HydroSphere .exe + Setup installer; pytest results; QA data-stitching report.

**Why this approach:** No existing artifacts; build PyInstaller → Inno Setup in order; QA after.

**What it will NOT do:** Feature changes; only fix confirmed bugs.

**Effort:** Large | **Risk:** Medium — Inno Setup may be unavailable

**Decisions to sanity-check:** Skip Inno if iscc.exe missing; fix only confirmed bugs

Your next move: approve this plan (already approved — proceed to $start-work) or ask questions. Full execution detail above.

---

> TL;DR (machine): Large effort, Medium risk, rebuild .exe+Setup + pytest + manual QA

## Scope
### Must have
- PyInstaller .exe built (dist/HydroSphere/HydroSphere.exe)
- Inno Setup Setup.exe built (installer_output/HydroSphere_*_Setup.exe) or documented unavailable
- pytest execution results reported
- Manual QA: load test_data_clean.xlsx / unified template → verify calculations
- Report any data-stitching errors (Excel parsing, analog correlation, curve fitting)

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No feature changes or new dependencies
- No refactoring beyond minimal bug fixes confirmed by QA
- Don't modify .py unless bug confirmed

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + manual QA
- Evidence: .omo/evidence/ulw/<session>/rebuild-installer-qa/
  - build_pyinstaller.log + build_inno.log
  - pytest_output.txt
  - qa_stitching_report.md

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Verify environment (pyinstaller, Inno Setup iscc, venv)
  What: Check pyinstaller in venv, check iscc.exe in PATH, verify build dirs exist.
  Must NOT: Modify source; only verify.
  References: build_installer.py:41-55, build.py, requirements.txt
  Acceptance: pyinstaller --version OK; iscc check gives path or "not installed"
  QA: happy (all found), failure (missing iscc — document, skip stage 2)
  Commit: N

- [ ] 2. PyInstaller build (.exe)
  What: python build.py → dist/HydroSphere/HydroSphere.exe
  Must NOT: Change build config unless required
  References: build.py:219-248, build_installer.py:74-137
  Acceptance: .exe exists and runs
  QA: happy (.exe launches); failure (build error — fix minimal)
  Commit: N

- [ ] 3. Inno Setup build (Setup.exe)
  What: python build_installer.py (stage 3) → installer_output/*.exe
  Must NOT: Skip if iscc unavailable; document instead
  References: build_installer.py:160-191, installer/hydrosphere_installer.iss
  Acceptance: Setup.exe exists or documented unavailable
  QA: happy (setup builds); failure (iscc missing — skip)
  Commit: N

- [ ] 4. Run pytest suite
  What: pytest tests/ with test data
  Must NOT: Skip failing tests without note
  References: test_*.py files, create_test_data.py, create_unified_template.py
  Acceptance: All tests pass or failures documented
  QA: happy (all pass); failure (failures noted with file/line)
  Commit: N

- [ ] 5. Manual QA — data stitching (Excel→calculation)
  What: Load test_data_clean.xlsx / unified template; verify calculations match expected
  Must NOT: Modify data sources; only verify
  References: gui/controller/data_controller.py:71-97 (load), core/stats/data_loader.py
  Acceptance: Data loads, calculations run, results consistent
  QA: happy (consistency); failure (mismatch documented with specific cell/module)
  Commit: N

- [ ] 6. Report findings (bugs/errors/stitching mismatches)
  What: Aggregate pytest + manual QA results into report
  Must NOT: Fix bugs not confirmed
  References: All previous steps
  Acceptance: Written report at .omo/evidence/rebuild-installer-qa/qa_report.md
  QA: happy (report complete); failure (report notes gaps)
  Commit: N

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit
- [ ] F2. Code quality review
- [ ] F3. Real manual QA
- [ ] F4. Scope fidelity
  What to do / Must NOT do: <...>
  Parallelization: Wave <N> | Blocked by: <...> | Blocks: <...>
  References (executor has NO interview context - be exhaustive): <src/path:lines>
  Acceptance criteria (agent-executable): <exact command or assertion>
  QA scenarios (name the exact tool + invocation): happy + failure, Evidence <attemptDir>/task-1-rebuild-installer-qa.<ext>
  Commit: <Y/N> | <type>(<scope>): <summary>

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [x] F1. Plan compliance audit — APPROVE
- [x] F2. Code quality review — APPROVE (build.py emoji bug fixed)
- [x] F3. Real manual QA — APPROVE (stitching gap found: Cyrillic Excel encoding)
- [x] F4. Scope fidelity — APPROVE

## Commit strategy

## Success criteria
