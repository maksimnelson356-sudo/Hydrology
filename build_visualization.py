r"""Generate standalone HTML project visualization for D:\hydrolib."""
import json
import os

ROOT = 'D:/hydrolib'

# Load file inventory
with open(os.path.join(ROOT, '_file_inventory.json'), encoding='utf-8') as f:
    files = json.load(f)

# Build folder tree
tree = {}
for entry in files:
    parts = entry['path'].split('\\')
    node = tree
    for part in parts:
        if part not in node:
            node[part] = {}
        node = node[part]

def tree_to_json(node, name='.', depth=0):
    result = {'name': name, 'children': [], '_files': []}
    for k, v in sorted(node.items()):
        if v:
            result['children'].append(tree_to_json(v, k, depth+1))
        else:
            result['_files'].append(k)
    if not result['children'] and not result['_files']:
        result['_files'].append(name)
    return result

# Sort children: dirs first, then files; alphabetical
def sort_tree(node):
    if 'children' in node:
        node['children'].sort(key=lambda c: (c['name'].startswith('_'), c['name'].lower()))
    if '_files' in node:
        node['_files'].sort()
    for c in node.get('children', []):
        sort_tree(c)

root_tree = tree_to_json(tree)
sort_tree(root_tree)

# File inventory with sizes
file_data = []
for entry in files:
    parts = entry['path'].split('\\')
    ext = entry['ext']
    size = entry['size']
    file_data.append({
        'path': entry['path'],
        'name': parts[-1],
        'ext': ext,
        'size': size,
        'dir': '\\'.join(parts[:-1]) if len(parts) > 1 else '.'
    })

# Module dependencies (from scan)
module_deps = {
    "gui/main_window.py": {
        "imports": ["PyQt6", "matplotlib", "numpy", "pandas", "scipy",
                    "gui.plot_style", "gui.controller", "core.stats", "core.gts_reference",
                    "core.hydrorash", "update_checker", "version"],
        "lines": 2897,
        "description": "Main application window with 17-tab navigation"
    },
    "gui/main_frozen.py": {
        "imports": ["PyQt6", "gui.plot_style", "gui.main_window", "update_checker", "version"],
        "lines": 78,
        "description": "Frozen build entry point with startup logging"
    },
    "gui/plot_style.py": {
        "imports": ["matplotlib", "PyQt6"],
        "lines": 566,
        "description": "Design system: colors, QSS stylesheet, matplotlib styling, icons"
    },
    "gui/controller/data_controller.py": {
        "imports": ["pandas", "PyQt6", "core.stats", "core.gts_reference", "core.hydrorash"],
        "lines": 168,
        "description": "Data loading, parsing, distribution, statistical calculations"
    },
    "gui/controller/plot_controller.py": {
        "imports": ["numpy", "PyQt6", "matplotlib"],
        "lines": 44,
        "description": "Plot building and figure saving"
    },
    "gui/controller/widget_factory.py": {
        "imports": ["PyQt6"],
        "lines": 88,
        "description": "Factory for creating work widgets (work1..work10, short)"
    },
    "gui/workers/calculation_workers.py": {
        "imports": ["PyQt6", "numpy", "pandas", "core.stats"],
        "lines": 239,
        "description": "Background calculation workers (Frequency, Homogeneity, Trend, etc.)"
    },
    "gui/widget_work1.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "gui.plot_style", "core.hydrorash"], "lines": 290, "description": "Work 1: Норма годового стока (annual flow norm)"},
    "gui/widget_work2.py": {"imports": ["numpy", "pandas", "PyQt6", "core.stats", "core.hydrorash"], "lines": 261, "description": "Work 2: Внутригодовое распределение (intra-annual distribution)"},
    "gui/widget_work3.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "core.hydrorash"], "lines": 175, "description": "Work 3: Минимальный сток (minimum flow)"},
    "gui/widget_work4.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "scipy", "core.hydrorash", "core.stats"], "lines": 615, "description": "Work 4: Максимальный сток/паводки (maximum flow/floods)"},
    "gui/widget_work5.py": {"imports": ["PyQt6", "core.hydrorash"], "lines": 296, "description": "Work 5: Ледовые явления (ice phenomena)"},
    "gui/widget_work6.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "core.hydrorash"], "lines": 226, "description": "Work 6: Водный баланс и экосистемный минимум (water balance)"},
    "gui/widget_work7.py": {"imports": ["numpy", "PyQt6", "matplotlib", "core.hydrorash"], "lines": 357, "description": "Work 7: Метод рациона, IDF, гидрографы, снеготаяние"},
    "gui/widget_work8.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "core.stats", "core.hydrorash"], "lines": 367, "description": "Work 8: FDC, регрессии, продвинутая статистика"},
    "gui/widget_work9.py": {"imports": ["numpy", "PyQt6", "matplotlib", "core.hydrorash"], "lines": 367, "description": "Work 9: ППУ, ГВП, регулирование (hydrotechnical)"},
    "gui/widget_work10.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "core.hydrorash", "core.stats"], "lines": 417, "description": "Work 10: Экология, базовый сток, спектр, засухи"},
    "gui/widget_short.py": {"imports": ["numpy", "pandas", "PyQt6", "matplotlib", "core.short_series"], "lines": 600, "description": "Short series restoration (<6 years)"},
    "core/stats/frequency.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 530, "description": "Frequency curves: Pearson III, Kritsky-Menkiel, empirical"},
    "core/stats/parameters.py": {"imports": ["numpy", "scipy"], "lines": 100, "description": "Statistical parameters calculation"},
    "core/stats/homogeneity.py": {"imports": ["scipy", "numpy"], "lines": 80, "description": "Homogeneity tests (12 criteria)"},
    "core/stats/trends.py": {"imports": ["scipy", "numpy", "pandas"], "lines": 120, "description": "Trend analysis (Mann-Kendall, Pettitt, Sen slope)"},
    "core/stats/composite_curves.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 90, "description": "Composite frequency curves"},
    "core/stats/confidence_bands.py": {"imports": ["numpy", "scipy"], "lines": 100, "description": "Bootstrap confidence bands"},
    "core/stats/series_extension.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Series extension by analog"},
    "core/stats/gts_integration.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 110, "description": "GTS classification and frequency curves"},
    "core/stats/critical_values.py": {"imports": ["numpy"], "lines": 60, "description": "Critical statistical values"},
    "core/stats/kritsky_tables.py": {"imports": ["numpy", "scipy"], "lines": 70, "description": "Kritsky-Menkiel ordinates tables"},
    "core/stats/spectral.py": {"imports": ["numpy", "scipy"], "lines": 90, "description": "Spectral analysis, Hurst exponent"},
    "core/stats/drought.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "SPI drought indices"},
    "core/stats/baseflow.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 70, "description": "Baseflow separation methods"},
    "core/stats/flow_duration.py": {"imports": ["numpy"], "lines": 60, "description": "Flow duration curve"},
    "core/stats/missing_data.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 60, "description": "Missing data detection and interpolation"},
    "core/stats/sheet_reader.py": {"imports": ["pandas", "numpy"], "lines": 100, "description": "Excel sheet reading"},
    "core/stats/data_loader.py": {"imports": ["pandas", "numpy"], "lines": 80, "description": "Hydrological data loading"},
    "core/stats/report.py": {"imports": ["pandas", "numpy"], "lines": 60, "description": "Report generation"},
    "core/stats/report_export.py": {"imports": ["pandas", "numpy", "openpyxl"], "lines": 50, "description": "Excel report export"},
    "core/stats/advanced_frequency.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 70, "description": "Advanced frequency analysis"},
    "core/stats/critical_values.py": {"imports": ["numpy"], "lines": 60, "description": "Critical values"},
    "core/hydrorash/rational_method.py": {"imports": ["numpy", "scipy"], "lines": 80, "description": "Rational method, IDF curves"},
    "core/hydrorash/flood_hydrograph.py": {"imports": ["numpy", "scipy"], "lines": 70, "description": "Flood hydrograph (triangular, gamma, unit)"},
    "core/hydrorash/reservoir_regulation.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Reservoir regulation"},
    "core/hydrorash/backwater.py": {"imports": ["numpy", "scipy"], "lines": 70, "description": "Backwater curve, normal/critical depth"},
    "core/hydrorash/ecological_flow.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Ecological flow (Tessmann method)"},
    "core/hydrorash/ice_phenomena.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 90, "description": "Ice phenomena calculations"},
    "core/hydrorash/intra_annual.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Intra-annual distribution"},
    "core/hydrorash/max_runoff.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Maximum runoff calculations"},
    "core/hydrorash/minimal_runoff.py": {"imports": ["numpy", "scipy"], "lines": 60, "description": "Minimal runoff (30-day)"},
    "core/hydrorash/snowmelt.py": {"imports": ["numpy"], "lines": 60, "description": "Snowmelt calculations"},
    "core/hydrorash/spillway.py": {"imports": ["numpy", "scipy"], "lines": 70, "description": "Spillway capacity, weir flow"},
    "core/hydrorash/water_balance.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 70, "description": "Water balance calculations"},
    "core/hydrorash/sedimentation.py": {"imports": ["numpy"], "lines": 50, "description": "Sedimentation calculations"},
    "core/hydrorash/hydrological_periods.py": {"imports": ["numpy", "pandas"], "lines": 50, "description": "Hydrological periods"},
    "core/hydrorash/regional_regressions.py": {"imports": ["numpy", "scipy"], "lines": 60, "description": "Regional regressions"},
    "core/hydrorash/utils.py": {"imports": ["numpy", "scipy"], "lines": 50, "description": "Shared utilities"},
    "core/hydraulics.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 60, "description": "Hydraulic calculations (composite Q)"},
    "core/profile.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Morphological profile, Q(H) curve"},
    "core/short_series.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 80, "description": "Short series fitting and restoration"},
    "core/gts_reference.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 60, "description": "GTS classification reference"},
    "version.py": {"imports": [], "lines": 33, "description": "Version info (2026.1.0)"},
    "build.py": {"imports": ["PyInstaller"], "lines": 50, "description": "PyInstaller build script"},
    "build_installer.py": {"imports": ["PyInstaller", "subprocess"], "lines": 249, "description": "Installer build (PyInstaller + Inno Setup)"},
    "create_template.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 179, "description": "Generate test data template"},
    "create_test_data.py": {"imports": ["numpy", "scipy", "pandas"], "lines": 53, "description": "Generate clean test data"},
}

# Tab info
tabs_info = [
    {"name": "Данные и статистика", "color": "#1565C0", "module": "tab_data", "desc": "Data loading, stats, homogeneity, outliers"},
    {"name": "Кривая обеспеченности", "color": "#1565C0", "module": "tab_graph", "desc": "Frequency curves (Pearson III, Kritsky-Menkiel)"},
    {"name": "Анализ трендов", "color": "#1565C0", "module": "tab_trend", "desc": "Mann-Kendall, Pettitt, Sen slope trend analysis"},
    {"name": "Визуализация", "color": "#1565C0", "module": "tab_viz", "desc": "Time series, histogram, boxplot, correlation heatmap"},
    {"name": "Крицкий-Менкель (ординаты)", "color": "#1565C0", "module": "tab_kritsky", "desc": "Kritsky-Menkiel ordinates table"},
    {"name": "Норма годового стока", "color": "#2E7D32", "module": "work1", "desc": "Annual flow norm (rational + analog)"},
    {"name": "Внутригодовое распределение", "color": "#00695C", "module": "work2", "desc": "Intra-annual distribution of flows"},
    {"name": "Минимальный сток", "color": "#E65100", "module": "work3", "desc": "Minimum flow (30-day)"},
    {"name": "Максимальный сток", "color": "#C62828", "module": "work4", "desc": "Maximum flow/floods, rating curve"},
    {"name": "Ледовые явления", "color": "#4527A0", "module": "work5", "desc": "Ice phenomena, ice thickness"},
    {"name": "Водный баланс", "color": "#00838F", "module": "work6", "desc": "Water balance, evaporation, ecological minimum"},
    {"name": "Рацион + IDF + Гидрографы", "color": "#6A1B9A", "module": "work7", "desc": "Rational method, IDF, hydrographs, snowmelt"},
    {"name": "FDC + Регрессии + Статистика", "color": "#2E7D32", "module": "work8", "desc": "Flow duration curve, regressions, advanced stats"},
    {"name": "ППУ + ГВП + Регулирование", "color": "#EF6C00", "module": "work9", "desc": "Weir capacity, backwater, reservoir regulation"},
    {"name": "Экология + Базовый сток", "color": "#880E4F", "module": "work10", "desc": "Ecological flow, baseflow, spectral, drought SPI"},
    {"name": "Короткие ряды (Short)", "color": "#F57C00", "module": "short", "desc": "Short series restoration (<6 years)"},
    {"name": "Параметры", "color": "#1565C0", "module": "tab_params", "desc": "Application parameters"},
]

# Tech stack
tech_stack = [
    {"name": "PyQt6", "version": ">=6.6", "cat": "GUI Framework", "desc": "Desktop application framework"},
    {"name": "matplotlib", "version": ">=3.8", "cat": "Plotting", "desc": "2D plotting library"},
    {"name": "numpy", "version": ">=1.26", "cat": "Numerical", "desc": "Array computing"},
    {"name": "scipy", "version": ">=1.11", "cat": "Scientific", "desc": "Statistical and scientific computing"},
    {"name": "pandas", "version": ">=2.1", "cat": "Data", "desc": "Data manipulation"},
    {"name": "openpyxl", "version": ">=3.1", "cat": "IO", "desc": "Excel file support"},
    {"name": "requests", "version": ">=2.31", "cat": "Network", "desc": "Update checker HTTP"},
    {"name": "pytest", "version": ">=8.0", "cat": "Testing", "desc": "Test framework"},
    {"name": "PyInstaller", "version": ">=6.0", "cat": "Packaging", "desc": "Executable bundler"},
]

# Count files by directory
dir_counts = {}
for entry in files:
    parts = entry['path'].split('\\')
    d = parts[0] if len(parts) > 1 else '.'
    dir_counts[d] = dir_counts.get(d, 0) + 1

# Count by extension category
ext_cats = {}
for entry in files:
    ext = entry['ext']
    if ext in ['.py']: ext_cats['Python'] = ext_cats.get('Python', 0) + 1
    elif ext in ['.json', '.md', '.txt', '.csv']: ext_cats['Data/Docs'] = ext_cats.get('Data/Docs', 0) + 1
    elif ext in ['.xlsx', '.xls']: ext_cats['Excel'] = ext_cats.get('Excel', 0) + 1
    elif ext in ['.pdf', '.docx']: ext_cats['Documents'] = ext_cats.get('Documents', 0) + 1
    elif ext in ['.svg', '.png', '.ico']: ext_cats['Images'] = ext_cats.get('Images', 0) + 1
    elif ext in ['.spec']: ext_cats['Config'] = ext_cats.get('Config', 0) + 1
    elif ext in ['.log']: ext_cats['Logs'] = ext_cats.get('Logs', 0) + 1
    elif ext in ['.hsp']: ext_cats['Data'] = ext_cats.get('Data', 0) + 1
    elif ext in ['.db']: ext_cats['Database'] = ext_cats.get('Database', 0) + 1
    else: ext_cats['Other'] = ext_cats.get('Other', 0) + 1

# Build the HTML
html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HydroSphere — Структура проекта</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', 'SF Pro Display', sans-serif; background: #FAFAFA; color: #212121; }}

/* HEADER */
.header {{ background: linear-gradient(135deg, #1A237E 0%, #0D47A1 100%); color: white; padding: 24px 32px; }}
.header h1 {{ font-size: 28px; font-weight: 700; }}
.header .subtitle {{ font-size: 14px; opacity: 0.8; margin-top: 4px; }}
.header .stats {{ display: flex; gap: 32px; margin-top: 16px; }}
.header .stat {{ text-align: center; }}
.header .stat .num {{ font-size: 24px; font-weight: 700; }}
.header .stat .label {{ font-size: 11px; opacity: 0.7; }}

/* NAV TABS */
.nav {{ background: white; border-bottom: 1px solid #E0E0E0; display: flex; gap: 0; overflow-x: auto; }}
.nav-tab {{ padding: 12px 20px; cursor: pointer; font-size: 13px; font-weight: 600; color: #757575; border-bottom: 3px solid transparent; white-space: nowrap; transition: all 0.2s; }}
.nav-tab:hover {{ color: #1565C0; background: #E3F2FD; }}
.nav-tab.active {{ color: #1565C0; border-bottom-color: #1565C0; }}

/* CONTENT */
.content {{ padding: 24px; max-width: 1400px; margin: 0 auto; }}
.section {{ display: none; }}
.section.active {{ display: block; }}
.section h2 {{ font-size: 20px; font-weight: 700; color: #1A237E; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #E3F2FD; }}

/* TREE */
.tree-container {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.node {{ cursor: pointer; }}
.node .header {{ display: flex; align-items: center; padding: 2px 4px; border-radius: 3px; font-size: 13px; }}
.node .header:hover {{ background: #E3F2FD; }}
.node .header .icon {{ width: 18px; text-align: center; margin-right: 4px; font-size: 14px; }}
.node .header .name {{ flex: 1; }}
.node .header .badge {{ font-size: 11px; color: #757575; background: #F5F5F5; padding: 1px 8px; border-radius: 10px; }}
.node .children {{ margin-left: 20px; border-left: 2px solid #E0E0E0; padding-left: 4px; }}
.node .file {{ padding: 2px 4px 2px 22px; font-size: 12px; color: #616161; }}
.node .file .ext {{ color: #1565C0; font-weight: 600; }}
.node .file .size {{ color: #BDBDBD; font-size: 11px; margin-left: 8px; }}

/* DEPENDENCY GRAPH */
.dep-container {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: relative; }}
.dep-container svg {{ width: 100%; height: 600px; }}

/* TABS MAP */
.tabs-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.tab-card {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #1565C0; }}
.tab-card .tab-name {{ font-weight: 700; font-size: 14px; }}
.tab-card .tab-desc {{ font-size: 12px; color: #757575; margin-top: 4px; }}

/* TECH STACK */
.tech-grid {{ display: flex; flex-wrap: wrap; gap: 12px; }}
.tech-card {{ background: white; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; }}
.tech-card .tech-name {{ font-weight: 700; font-size: 14px; color: #1565C0; }}
.tech-card .tech-version {{ font-size: 11px; color: #757575; }}
.tech-card .tech-desc {{ font-size: 11px; color: #9E9E9E; margin-top: 2px; }}

/* FLOW DIAGRAM */
.flow-container {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.flow-step {{ display: inline-flex; align-items: center; padding: 12px 20px; border-radius: 8px; margin: 8px; font-weight: 600; font-size: 13px; color: white; }}
.flow-arrow {{ font-size: 24px; color: #1565C0; margin: 0 8px; }}
.flow-row {{ display: flex; align-items: center; justify-content: center; flex-wrap: wrap; }}

/* DATA FLOW */
.df-container {{ background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.df-box {{ border: 2px solid #1565C0; border-radius: 8px; padding: 16px; text-align: center; font-weight: 600; background: #E3F2FD; }}
.df-box .step-num {{ font-size: 11px; color: #757575; }}
.df-box .step-name {{ font-size: 14px; color: #1A237E; }}
.df-line {{ text-align: center; font-size: 20px; color: #1565C0; margin: 4px 0; }}

/* FILE LIST */
.file-list {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); max-height: 600px; overflow-y: auto; }}
.file-row {{ display: flex; align-items: center; padding: 4px 8px; font-size: 12px; border-bottom: 1px solid #F5F5F5; }}
.file-row:hover {{ background: #F5F5F5; }}
.file-row .f-ext {{ color: #1565C0; font-weight: 600; width: 40px; }}
.file-row .f-name {{ flex: 1; }}
.file-row .f-size {{ color: #BDBDBD; font-size: 11px; }}
.file-row .f-dir {{ color: #9E9E9E; font-size: 11px; width: 200px; }}

/* SEARCH */
.search-bar {{ margin-bottom: 16px; }}
.search-bar input {{ width: 100%; padding: 10px 16px; border: 2px solid #E0E0E0; border-radius: 8px; font-size: 14px; }}
.search-bar input:focus {{ border-color: #1565C0; outline: none; }}

/* LEGEND */
.legend {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}

/* Stats summary */
.stats-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
.stat-card {{ background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; min-width: 120px; }}
.stat-card .stat-num {{ font-size: 28px; font-weight: 700; color: #1565C0; }}
.stat-card .stat-label {{ font-size: 12px; color: #757575; }}

/* Module mini-cards */
.module-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-bottom: 24px; }}
.module-card {{ background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-top: 3px solid #1565C0; }}
.module-card .mod-name {{ font-weight: 700; font-size: 12px; }}
.module-card .mod-files {{ font-size: 11px; color: #757575; }}
.module-card .mod-lines {{ font-size: 11px; color: #9E9E9E; }}

.tooltip {{ position: absolute; background: rgba(0,0,0,0.85); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 100; }}
</style>
</head>
<body>
<div class="header">
    <h1>HydroSphere — Структура проекта</h1>
    <div class="subtitle">Платформа гидрологической статистики — интерактивная визуализация архитектуры</div>
    <div class="stats">
        <div class="stat"><div class="num">{len(files)}</div><div class="label">Файлов</div></div>
        <div class="stat"><div class="num">{len(set(f['path'].split(chr(92))[0] for f in files))}</div><div class="label">Директорий</div></div>
        <div class="stat"><div class="num">{len(tabs_info)}</div><div class="label">Вкладок</div></div>
        <div class="stat"><div class="num">{len(module_deps)}</div><div class="label">Модулей</div></div>
    </div>
</div>

<div class="nav">
    <div class="nav-tab active" data-tab="overview">Обзор</div>
    <div class="nav-tab" data-tab="tree">📁 Дерево файлов</div>
    <div class="nav-tab" data-tab="deps">🔗 Зависимости</div>
    <div class="nav-tab" data-tab="tabs">📑 Вкладки</div>
    <div class="nav-tab" data-tab="flow">🔄 Поток данных</div>
    <div class="nav-tab" data-tab="tech">🛠 Стек технологий</div>
    <div class="nav-tab" data-tab="files">📋 Полный список файлов</div>
</div>

<div class="content">
    <!-- OVERVIEW -->
    <div class="section active" id="section-overview">
        <h2>Обзор проекта</h2>
        <div class="stats-row">
            <div class="stat-card"><div class="stat-num">{len(files)}</div><div class="stat-label">Всего файлов</div></div>
            <div class="stat-card"><div class="stat-num">{len(tabs_info)}</div><div class="stat-label">Вкладок в UI</div></div>
            <div class="stat-card"><div class="stat-num">{len([f for f in files if f['ext']=='.py'])}</div><div class="stat-label">Python файлов</div></div>
            <div class="stat-card"><div class="stat-num">{len(tabs_info)}</div><div class="stat-label">Модулей core/</div></div>
        </div>
        <div class="legend">
            <div class="legend-item"><div class="legend-dot" style="background:#1565C0"></div> GUI / основной</div>
            <div class="legend-item"><div class="legend-dot" style="background:#2E7D32"></div> Статистика</div>
            <div class="legend-item"><div class="legend-dot" style="background:#C62828"></div> Максимальный сток</div>
            <div class="legend-item"><div class="legend-dot" style="background:#E65100"></div> Минимальный сток</div>
            <div class="legend-item"><div class="legend-dot" style="background:#4527A0"></div> Ледовые явления</div>
            <div class="legend-item"><div class="legend-dot" style="background:#00838F"></div> Водный баланс</div>
            <div class="legend-item"><div class="legend-dot" style="background:#6A1B9A"></div> Гидротехнические</div>
            <div class="legend-item"><div class="legend-dot" style="background:#F57C00"></div> Short / экология</div>
        </div>
        <h3 style="margin-bottom:8px;">Структура директорий</h3>
        <div class="module-grid" id="dir-overview"></div>
    </div>

    <!-- TREE -->
    <div class="section" id="section-tree">
        <h2>📁 Дерево файлов проекта</h2>
        <div class="search-bar"><input type="text" id="tree-search" placeholder="Поиск файлов..."></div>
        <div class="tree-container" id="tree-container"></div>
    </div>

    <!-- DEPENDENCIES -->
    <div class="section" id="section-deps">
        <h2>🔗 Граф зависимостей модулей</h2>
        <div class="dep-container"><svg id="dep-graph"></svg></div>
    </div>

    <!-- TABS -->
    <div class="section" id="section-tabs">
        <h2>📑 Карта вкладок (17 штук)</h2>
        <div class="tabs-grid" id="tabs-grid"></div>
    </div>

    <!-- DATA FLOW -->
    <div class="section" id="section-flow">
        <h2>🔄 Поток данных</h2>
        <div class="df-container" id="data-flow"></div>
        <h3 style="margin-top:24px;margin-bottom:8px;">Расчётные воркеры (фоновые потоки)</h3>
        <div class="flow-container" id="workers-flow"></div>
    </div>

    <!-- TECH STACK -->
    <div class="section" id="section-tech">
        <h2>🛠 Стек технологий</h2>
        <div class="tech-grid" id="tech-grid"></div>
    </div>

    <!-- FILE LIST -->
    <div class="section" id="section-files">
        <h2>📋 Полный список файлов</h2>
        <div class="search-bar"><input type="text" id="file-search" placeholder="Фильтр файлов..."></div>
        <div class="file-list" id="file-list"></div>
    </div>
</div>

<script>
const FILES = {json.dumps(file_data, ensure_ascii=False)};
const MODULE_DEPS = {json.dumps(module_deps, ensure_ascii=False, default=str)};
const TABS_INFO = {json.dumps(tabs_info, ensure_ascii=False)};
const TECH_STACK = {json.dumps(tech_stack, ensure_ascii=False)};
const DIR_COUNTS = {json.dumps(dir_counts, ensure_ascii=False)};
</script>
<script>
// ===== NAVIGATION =====
document.querySelectorAll('.nav-tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('section-' + tab.dataset.tab).classList.add('active');
    }});
}});

// ===== OVERVIEW: DIR CARDS =====
const dirColors = {{'gui':'#1565C0','core':'#2E7D32','i18n':'#4527A0','tools':'#E65100','build':'#757575','.claude':'#9E9E9E','.codegraph':'#9E9E9E'}};
const dirOverview = document.getElementById('dir-overview');
Object.entries(DIR_COUNTS).sort((a,b) => b[1]-a[1]).forEach(([dir, count]) => {{
    const card = document.createElement('div');
    card.className = 'module-card';
    card.style.borderTopColor = dirColors[dir] || '#1565C0';
    const pyCount = FILES.filter(f => f.dir === dir && f.ext === '.py').length;
    card.innerHTML = `<div class="mod-name">${{dir}}/</div><div class="mod-files">${{count}} файлов (${{pyCount}} .py)</div>`;
    dirOverview.appendChild(card);
}});

// ===== TREE =====
function buildTree(files) {{
    const tree = {{}};
    files.forEach(f => {{
        const parts = f.path.split('\\\\');
        let node = tree;
        for (const part of parts) {{
            if (!node[part]) node[part] = {{}};
            node = node[part];
        }}
    }});
    return tree;
}}

function renderTree(node, path, container, depth) {{
    const entries = Object.entries(node).sort((a,b) => {{
        const aDir = !FILES.some(f => f.path.startsWith(path+'\\\\'+a[0]+'\\\\'));
        const bDir = !FILES.some(f => f.path.startsWith(path+'\\\\'+b[0]+'\\\\'));
        if (aDir !== bDir) return aDir ? -1 : 1;
        return a[0].localeCompare(b[0], 'ru');
    }});
    
    entries.forEach(([name, children]) => {{
        const fullPath = path ? path + '\\\\' + name : name;
        const fileCount = FILES.filter(f => f.path.startsWith(fullPath+'\\\\')).length;
        const directFiles = FILES.filter(f => f.path.split('\\\\').slice(0,-1).join('\\\\') === fullPath);
        const isDir = fileCount > 0 || Object.keys(children).length > 0;
        
        const el = document.createElement('div');
        el.className = 'node';
        
        const header = document.createElement('div');
        header.className = 'header';
        const icon = isDir ? '📂' : '📄';
        header.innerHTML = `<span class="icon">${{icon}}</span><span class="name">${{name}}</span>`;
        if (isDir) {{
            header.innerHTML += `<span class="badge">${{fileCount}} файлов</span>`;
        }} else if (directFiles.length > 0) {{
            const f = directFiles[0];
            header.innerHTML += `<span class="badge" style="color:#1565C0">${{formatSize(f.size)}}</span>`;
        }}
        el.appendChild(header);
        
        if (isDir) {{
            const childContainer = document.createElement('div');
            childContainer.className = 'children';
            renderTree(children, fullPath, childContainer, depth+1);
            el.appendChild(childContainer);
        }}
        container.appendChild(el);
    }});
}}

function formatSize(bytes) {{
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' КБ';
    return (bytes/(1024*1024)).toFixed(1) + ' МБ';
}}

function initTree() {{
    const tree = buildTree(FILES);
    const container = document.getElementById('tree-container');
    renderTree(tree, '', container, 0);
}}

document.getElementById('tree-search').addEventListener('input', function() {{
    const q = this.value.toLowerCase();
    document.querySelectorAll('#tree-container .node').forEach(n => {{
        const name = n.querySelector('.name').textContent.toLowerCase();
        n.style.display = name.includes(q) ? '' : 'none';
    }});
}});

// ===== DEPENDENCY GRAPH =====
function initDepGraph() {{
    const svg = d3.select('#dep-graph');
    const width = svg.node().getBoundingClientRect().width || 1200;
    const height = 600;
    
    // Extract unique modules and their categories
    const modules = Object.entries(MODULE_DEPS).map(([path, info]) => ({{
        id: path,
        name: path.split('\\\\').pop(),
        category: path.startsWith('gui/') ? 'GUI' : path.startsWith('core/') ? 'Core' : 'Other',
        lines: info.lines || 0,
        description: info.description || ''
    }}));
    
    // Build links from imports
    const links = [];
    modules.forEach(m => {{
        const imports = MODULE_DEPS[m.id]?.imports || [];
        imports.forEach(imp => {{
            // Find matching module
            const target = modules.find(t => t.id.includes(imp.replace('gui/', '').replace('core/', '')) || imp.replace('gui/','').replace('core/','') === t.name);
            if (target && target.id !== m.id) {{
                links.push({{source: m.id, target: target.id}});
            }}
        }});
    }});
    
    const simulation = d3.forceSimulation(modules)
        .force('link', d3.forceLink(links).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width/2, height/2))
        .force('collision', d3.forceCollide().radius(40));
    
    const g = svg.append('g');
    
    // Zoom
    svg.call(d3.zoom().scaleExtent([0.3, 3]).on('zoom', e => g.attr('transform', e.transform)));
    
    // Category colors
    const catColors = {{'GUI':'#1565C0', 'Core':'#2E7D32', 'Other':'#9E9E9E'}};
    
    const link = g.append('g').selectAll('line').data(links).enter().append('line')
        .attr('stroke', '#E0E0E0').attr('stroke-width', 1);
    
    const node = g.append('g').selectAll('g').data(modules).enter().append('g')
        .call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));
    
    node.append('rect').attr('width', 140).attr('height', 32).attr('rx', 6)
        .attr('fill', d => catColors[d.category] || '#9E9E9E')
        .attr('opacity', 0.9);
    
    node.append('text').text(d => d.name).attr('x', 70).attr('y', 20)
        .attr('text-anchor', 'middle').attr('fill', 'white').attr('font-size', 10).attr('font-weight', 600);
    
    node.append('title').text(d => d.description);
    
    node.on('mouseover', function(event, d) {{
        d3.select(this).select('rect').attr('opacity', 1).attr('stroke', '#1A237E').attr('stroke-width', 2);
    }}).on('mouseout', function(event, d) {{
        d3.select(this).select('rect').attr('opacity', 0.9).attr('stroke', 'none');
    }});
    
    simulation.on('tick', () => {{
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => `translate(${{d.x - 70}},${{d.y - 16}})`);
    }});
    
    function dragstarted(event) {{ event.sourceEvent.stopPropagation(); }}
    function dragged(event, d) {{ d.fx = event.x; d.fy = event.y; }}
    function dragended(event, d) {{ d.fx = null; d.fy = null; }}
}}

// ===== TABS =====
function initTabs() {{
    const grid = document.getElementById('tabs-grid');
    TABS_INFO.forEach(tab => {{
        const card = document.createElement('div');
        card.className = 'tab-card';
        card.style.borderLeftColor = tab.color;
        card.innerHTML = `<div class="tab-name" style="color:${{tab.color}}">${{tab.name}}</div><div class="tab-desc">${{tab.desc}}</div>`;
        grid.appendChild(card);
    }});
}}

// ===== DATA FLOW =====
function initDataFlow() {{
    const flow = document.getElementById('data-flow');
    const steps = [
        {{num:'1', name:'Excel файл (.xlsx)', color:'#1565C0'}},
        {{num:'2', name:'DataController.load_from_file()', color:'#0D47A1'}},
        {{num:'3', name:'_parse_work_sheets()', color:'#1565C0'}},
        {{num:'4', name:'_all_posts dict', color:'#E3F2FD', light:true}},
        {{num:'5', name:'CalculationWorker (QThread)', color:'#2E7D32'}},
        {{num:'6', name:'core.stats расчёты', color:'#2E7D32'}},
        {{num:'7', name:'FigureCanvas (matplotlib)', color:'#FF6F00'}},
        {{num:'8', name:'Пользователь видит график', color:'#C62828'}},
    ];
    let html = '<div class="flow-row">';
    steps.forEach((s, i) => {{
        if (i > 0) html += '<span class="flow-arrow">→</span>';
        html += `<div class="df-box" style="border-color:${{s.color}}; background:${{s.light ? '#E3F2FD' : s.color}}"><div class="step-num">Шаг ${{s.num}}</div><div class="step-name">${{s.name}}</div></div>`;
    }});
    html += '</div>';
    flow.innerHTML = html;
    
    // Workers
    const wf = document.getElementById('workers-flow');
    const workers = [
        {{name:'FrequencyCurveWorker', desc:'Кривая обеспеченности'}},
        {{name:'HomogeneityWorker', desc:'Проверка однородности'}},
        {{name:'TrendWorker', desc:'Анализ тренда'}},
        {{name:'CompositeCurveWorker', desc:'Составная кривая'}},
        {{name:'ExtensionWorker', desc:'Удлинение ряда'}},
        {{name:'KritskyWorker', desc:'Ординаты Крицкого-Менкеля'}},
        {{name:'AutoCsCvWorker', desc:'Автоподбор Cs/Cv'}},
        {{name:'HistoricalExtremesWorker', desc:'Исторические экстремумы'}},
        {{name:'GTSIntegrationWorker', desc:'GTS интеграция'}},
        {{name:'ConfidenceBandsWorker', desc:'Доверительные полосы'}},
    ];
    let whtml = '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
    workers.forEach(w => {{
        whtml += `<div class="df-box" style="border-color:#2E7D32;background:#E8F5E9;min-width:150px"><div class="step-name">${{w.name}}</div><div class="step-num">${{w.desc}}</div></div>`;
    }});
    whtml += '</div>';
    wf.innerHTML = whtml;
}}

// ===== TECH STACK =====
function initTech() {{
    const grid = document.getElementById('tech-grid');
    TECH_STACK.forEach(t => {{
        const card = document.createElement('div');
        card.className = 'tech-card';
        card.innerHTML = `<div class="tech-name">${{t.name}}</div><div class="tech-version">${{t.version}}</div><div class="tech-desc">${{t.desc}}</div>`;
        grid.appendChild(card);
    }});
}}

// ===== FILE LIST =====
function initFileList() {{
    const list = document.getElementById('file-list');
    function render(filtered) {{
        list.innerHTML = '';
        filtered.forEach(f => {{
            const row = document.createElement('div');
            row.className = 'file-row';
            const ext = f.ext || '(none)';
            row.innerHTML = `<span class="f-ext">${{ext}}</span><span class="f-name">${{f.name}}</span><span class="f-dir">${{f.dir}}</span><span class="f-size">${{formatSize(f.size)}}</span>`;
            list.appendChild(row);
        }});
    }}
    render(FILES);
    document.getElementById('file-search').addEventListener('input', function() {{
        const q = this.value.toLowerCase();
        render(FILES.filter(f => f.name.toLowerCase().includes(q) || f.dir.toLowerCase().includes(q) || f.ext.toLowerCase().includes(q)));
    }});
}}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {{
    initTree();
    initDepGraph();
    initTabs();
    initDataFlow();
    initTech();
    initFileList();
    // Trigger dep graph resize after layout
    setTimeout(() => {{ d3.select('#dep-graph').attr('width', document.getElementById('dep-graph').getBoundingClientRect().width); }}, 100);
}});
</script>
</body>
</html>"""

# Write the HTML
output_path = os.path.join(ROOT, 'docs', 'project-viz.html')
os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Written: {output_path}")
print(f"Size: {len(html)} chars ({len(html)/1024:.1f} KB)")
