---
slug: visualization-folder-structure
status: awaiting-approval
intent: clear
review_required: false
pending-action: write .omo/plans/visualization-folder-structure.md
approach: >
  Explore the D:\hydrolib project, understand its folder structure,
  module relationships, and data flows. Plan a beautiful visualization
  (HTML/D3.js interactive project map) that shows:
  1) Full folder tree with file sizes and types
  2) Module dependency graph (core/gui/workers relationships)
  3) Data flow from Excel -> DataController -> CalculationWorkers -> plots
  4) Tab navigation map (17 tabs and their purposes)
  5) Technology stack visualization
  The plan will be executed as a standalone HTML visualization
  that lives alongside the project.
---

# Draft: visualization-folder-structure

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
<!-- id | outcome (one line) | status: active|deferred | evidence path -->
<!-- COMP-1 | Scan full folder structure and file inventory | active | codegraph_explore of D:\hydrolib -->
<!-- COMP-2 | Map module dependencies and data flows | active | codegraph_explore of core/ and gui/ -->
<!-- COMP-3 | Identify visualization patterns currently in use | active | codegraph_explore of plot_style.py, widget_*.py -->
<!-- COMP-4 | Design and build the HTML/D3.js visualization | deferred | .omo/plans/visualization-folder-structure.md -->
<!-- COMP-5 | Add export/feature toggle to save viz as standalone HTML | deferred | .omo/plans/visualization-folder-structure.md -->

## Open assumptions (announced defaults)
<!-- Intent is CLEAR: research resolves ambiguity, defaults are adopted (not asked), and each is surfaced in the plan's human TL;DR for veto. -->
<!-- assumption | adopted default | rationale | reversible? -->
<!-- visualization format | standalone HTML with D3.js | best practice for shareable, interactive project maps, zero dependencies beyond a browser | yes -->
<!-- scope | full project folder visualization | user asked for visualization of the folder the program is run from | yes -->
<!-- technology | Python + D3.js (generated HTML) | matches project stack and produces best-looking interactive output | yes -->

## Findings (cited - path:lines)

### Folder structure (D:\hydrolib)
- 70+ files, 15 subdirectories
- Key directories: core/, core/stats/ (22 files), core/hydrorash/ (19 files), gui/, gui/workers/, gui/controller/, gui/resources/ (16 SVG icons), i18n/, build/, dist/, installer/, tests/
- Entry points: gui/main_window.py (MainWindow), gui/main_frozen.py (frozen build entry), build.py, build_installer.py
- Config files: version.py, requirements.txt, .spec files (HydroSphere.spec, ГидроСтатистика_2026.spec)
- Data templates: шаблон_данных.xlsx, create_template.py

### Core modules (D:\hydrolib\core\)
- core/gts_reference.py: GTS classification
- core/hydraulics.py: hydraulic calculations (composite Q)
- core/profile.py: MorphoProfile, ProfilePoint for Q(H) curves
- core/short_series.py: short series restoration
- core/stats/ (22 files): frequency.py, parameters.py, homogeneity.py, trends.py, composite_curves.py, confidence_bands.py, gts_integration.py, series_extension.py, kritsky_tables.py, missing_data.py, sheet_reader.py, data_loader.py, flow_duration.py, spectral.py, drought.py, baseflow.py, report.py, report_export.py, critical_values.py, advanced_frequency.py
- core/hydrorash/ (19 files): rational_method.py, flood_hydrograph.py, reservoir_regulation.py, backwater.py, ecological_flow.py, ice_phenomena.py, intra_annual.py, max_runoff.py, minimal_runoff.py, snowmelt.py, spillway.py, water_balance.py, sedimentation.py, utils.py

### GUI modules (D:\hydrolib\gui\)
- gui/main_window.py: MainWindow class (2897 lines), 17 tabs, QListWidget sidebar navigation, QStackedWidget
- gui/main_frozen.py: frozen build entry point
- gui/plot_style.py: design system (colors, QSS stylesheet, matplotlib styling, icons, fonts)
- gui/controller/: DataController, PlotController, widget_factory.py (BaseWorkWidget + create_work_widget)
- gui/workers/: CalculationWorker (base) + FrequencyCurveWorker, HomogeneityWorker, TrendWorker, CompositeCurveWorker, ExtensionWorker, KritskyWorker, AutoCsCvWorker, HistoricalExtremesWorker, GTSIntegrationWorker, ConfidenceBandsWorker
- gui/widget_work1.py..widget_work10.py: individual work tab widgets (each has Figure + FigureCanvas)
- gui/widget_short.py: short series restoration widget
- gui/resources/: 16 SVG icons + logo

### Visualization currently in use
- matplotlib FigureCanvasQTAgg embedded in PyQt6 widgets (per-widget)
- gui/plot_style.py: apply_global_style(), setup_axes_style(), add_info_box() - defined but inconsistently applied
- plot_style.py COLORS dict: Material Design Blue palette (#1565C0 primary, etc.)
- QSS stylesheet via build_stylesheet() for Qt widgets
- Each work widget owns its own Figure(figsize=...) - no shared figure manager
- No interactive plots (zoom/pan/hover tooltips) beyond basic matplotlib
- No seaborn/plotly/bokeh used

### Data flow
- Excel file -> DataController.load_from_file() -> _parse_work_sheets() -> _all_posts dict
- Each post name mapped to a worksheet (work1..work10)
- CalculationWorkers run in background QThreads, emit progress/finished signals
- Results displayed in QTextEdit + FigureCanvas per widget

## Decisions (with rationale)
- visualization format: standalone HTML + D3.js, self-contained, can be opened in any browser
- output location: D:\hydrolib\docs\project-viz.html (or similar)
- scope: full folder visualization including dependency graph, data flows, and module map

## Scope IN
- Full folder tree visualization with file types and sizes
- Module dependency graph (core/gui relationships)
- Tab navigation map showing all 17 tabs and their purposes
- Data flow diagram (Excel -> DataController -> CalculationWorkers -> Plots)
- Technology stack visualization
- Color scheme derived from project's own COLORS dict
- Responsive/interactive HTML output

## Scope OUT (Must NOT have)
- No modifications to any Python source files
- No changes to the application itself - only a standalone visualization artifact
- No third-party dependencies beyond D3.js (CDN) and Python stdlib
- No implementation of new features in the application

## Open questions
- (none - all decisions made from exploration)

## Approval gate
status: awaiting-approval
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
