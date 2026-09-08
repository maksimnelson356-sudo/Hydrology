import os

root = 'D:/hydrolib'
skip = {'venv', '__pycache__', 'dist', 'build', 'installer_output'}
deps = {}
py_files = []
for dp, dn, fns in os.walk(root):
    if any(s in dp for s in skip):
        continue
    for f in fns:
        if f.endswith('.py'):
            rel = os.path.relpath(os.path.join(dp, f), root)
            py_files.append(rel)
            with open(os.path.join(root, rel), encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            module_imports = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('from ') and ' import ' in line:
                    mod = line.split('from ')[1].split(' import')[0].strip()
                    module_imports.append(mod)
                elif line.startswith('import ') and ' as ' not in line:
                    mod = line.split('import ')[1].strip().split('.')[0]
                    module_imports.append(mod)
            deps[rel] = {'imports': module_imports}

print(f'Python files analyzed: {len(py_files)}')
print()
for p in sorted(deps.keys()):
    print(f'{p}: {len(deps[p]["imports"])} imports')
