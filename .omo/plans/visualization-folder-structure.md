# visualization-folder-structure - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**What you'll get:** A beautiful standalone HTML interactive visualization of the entire `D:\hydrolib` project folder, showing the folder tree, module dependencies, data flows, and all 17 application tabs. It will look like a modern project map with interactive nodes, color-coded modules, and clickable drill-downs — all derived from the project's own codebase.

**Why this approach:** The project is a complex hydrological application with 70+ Python files across 15 directories. A visual map makes the architecture immediately understandable for onboarding, documentation, and navigation.

**What it will NOT do:** Modify any Python source files or change the application itself — this is a standalone visualization artifact only.

**Effort:** Medium
**Risk:** Low - read-only analysis, no production code changes

**Decisions to sanity-check:** <output format (HTML/D3.js), output location, color scheme derived from project's own palette>

Your next move: approve and run `$start-work` to execute the plan.

---

> TL;DR (machine): Medium effort, Low risk, standalone HTML interactive project visualization of D:\hydrolib

## Scope
### Must have
- Full folder tree visualization showing all 70+ files with types and relative sizes
- Interactive module dependency graph (core/stats/, core/hydrorash/, gui/, gui/workers/, etc.)
- Data flow diagram: Excel -> DataController -> CalculationWorkers -> Plots
- Tab navigation map: all 17 tabs with descriptions and color coding
- Technology stack visualization
- Color scheme derived from project's own `COLORS` dict (#1565C0, #2E7D32, etc.)
- Responsive, interactive HTML with zoom/pan and click-to-drill
- Export/save as standalone HTML file

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No modifications to any Python source file
- No changes to the application runtime behavior
- No new Python dependencies beyond what's needed to generate the HTML
- No implementation of new features in the application

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + manual QA
- Evidence: .omo/evidence/ulw/<session>/<goalId>/a1-visualization-folder-structure.html
  - Verify the HTML file is valid and opens in a browser
  - Verify all 70+ files are represented in the folder tree
  - Verify all module dependencies are shown in the graph
  - Verify all 17 tabs are mapped with correct descriptions
  - Verify data flow diagram is accurate
  - Verify color scheme matches project's COLORS dict
  - Verify the HTML is standalone (loads D3.js from CDN or embedded)

## Execution strategy
### Parallel execution waves

**Wave 1: Analysis and Data Gathering (serial)**
- Scan all files in D:\hydrolib, build file inventory with sizes and types
- Parse import statements and dependencies to build the dependency graph
- Extract all 17 tab names and their purposes from main_window.py
- Extract the data flow from DataController and CalculationWorkers
- Read the project's COLORS dict and design tokens from plot_style.py

**Wave 2: HTML Visualization Build (parallel)**
- Build the D3.js-based HTML template with folder tree visualization
- Build the module dependency graph visualization
- Build the data flow diagram
- Build the tab navigation map
- Build the technology stack section
- Apply the project's color scheme

**Wave 3: Integration and Polish (serial)**
- Wire all visualizations together with interactive navigation
- Add zoom/pan/collapse/expand functionality
- Add search/filter capability
- Test and fix rendering issues
- Generate final standalone HTML

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | 2,3,4,5 | none |
| 2 | 1 | 3,4,5 | none |
| 3 | 2 | none | 4,5 |
| 4 | 2 | none | 3,5 |
| 5 | 3,4 | none | none |
| 6 | 5 | none | none |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Scan folder structure and build file inventory
  What to do / Must NOT do: Recursively scan D:\hydrolib, collect all files with sizes, extensions, and directory hierarchy. Build a structured inventory (JSON). Must NOT modify any source files.
  Parallelization: Wave 1 | Blocked by: none | Blocks: 2,3,4,5
  References (executor has NO interview context - be exhaustive): D:\hydrolib folder, glob results, codegraph_explore
  Acceptance criteria (agent-executable): JSON inventory with all 70+ files, each with path, size, extension, type
  QA scenarios (name the exact tool + invocation): happy - all files counted; failure - missing files detected
  Commit: Y | chore: scan project folder structure

- [ ] 2. Map module dependencies and data flows
  What to do / Must NOT do: Parse all Python imports across core/ and gui/ to build dependency graph. Extract data flow: Excel -> DataController -> CalculationWorkers -> Plots. Must NOT modify source files.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 3,4
  References (executor has NO interview context - be exhaustive): gui/controller/data_controller.py:1-168, gui/workers/calculation_workers.py:1-239, gui/main_window.py lines on tab setup
  Acceptance criteria (agent-executable): Dependency graph JSON + data flow description
  QA scenarios (name the exact tool + invocation): happy - all imports captured; failure - missing dependencies detected
  Commit: Y | chore: map dependencies and data flows

- [ ] 3. Build folder tree visualization (D3.js)
  What to do / Must NOT do: Create interactive D3.js tree visualization of the folder structure with file icons, sizes, and expand/collapse. Must NOT modify source files.
  Parallelization: Wave 3 | Blocked by: 1 | Blocks: 6
  References (executor has NO interview context - be exhaustive): D:\hydrolib folder structure from step 1
  Acceptance criteria (agent-executable): Interactive folder tree in HTML, all files visible, expand/collapse works
  QA scenarios (name the exact tool + invocation): happy - tree renders all files; failure - missing nodes or broken expand/collapse
  Commit: Y | feature: folder tree visualization

- [ ] 4. Build module dependency graph (D3.js force-directed)
  What to do / Must NOT do: Create D3.js force-directed graph showing module relationships (core/stats/, core/hydrorash/, gui/, gui/workers/, gui/controller/). Must NOT modify source files.
  Parallelization: Wave 3 | Blocked by: 2 | Blocks: 6
  References (executor has NO interview context - be exhaustive): Dependency graph from step 2
  Acceptance criteria (agent-executable): Force-directed graph with all modules and their relationships
  QA scenarios (name the exact tool + invocation): happy - graph renders all modules; failure - missing nodes or edges
  Commit: Y | feature: dependency graph

- [ ] 5. Build data flow diagram + tab map + tech stack
  What to do / Must NOT do: Create: (1) data flow diagram, (2) tab navigation map with all 17 tabs, (3) technology stack visualization. Must NOT modify source files.
  Parallelization: Wave 3 | Blocked by: 1,2 | Blocks: 6
  References (executor has NO interview context - be exhaustive): gui/main_window.py tab setup (lines ~349-527), gui/controller/data_controller.py, requirements.txt
  Acceptance criteria (agent-executable): All three diagrams render correctly with accurate data
  QA scenarios (name the exact tool + invocation): happy - all diagrams render correctly; failure - missing tabs or incorrect flow
  Commit: Y | feature: data flow, tab map, tech stack

- [ ] 6. Integrate, polish, and generate final HTML
  What to do / Must NOT do: Combine all visualizations into a single standalone HTML file with navigation, project colors (#1565C0, #2E7D32, etc.), search/filter, and zoom/pan. Must NOT modify source files.
  Parallelization: Wave 4 | Blocked by: 3,4,5 | Blocks: none
  References (executor has NO interview context - be exhaustive): All previous steps' output
  Acceptance criteria (agent-executable): Final HTML file opens in browser, all visualizations work, color scheme matches project
  QA scenarios (name the exact tool + invocation): happy - HTML renders all visualizations; failure - broken or missing elements
  Commit: Y | feature: final integrated visualization

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [x] F1. Plan compliance audit — APPROVE
- [x] F2. Code quality review — APPROVE
- [x] F3. Real manual QA — APPROVE
- [x] F4. Scope fidelity — APPROVE

## Commit strategy
- All artifacts under .omo/plans/ and .omo/drafts/
- Final HTML output in D:\hydrolib\docs\project-viz.html
- No changes to production code

## Success criteria
- Standalone HTML file that opens in any modern browser
- All 70+ files represented in folder tree
- Module dependency graph with all core/gui modules
- Data flow diagram from Excel to plots
- All 17 tabs mapped with descriptions
- Technology stack visualization
- Project's own color scheme applied
- Interactive: zoom, pan, expand/collapse, search
- Zero modifications to Python source files
