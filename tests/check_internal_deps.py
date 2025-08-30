# Ensure repo root is on sys.path so imports like `import code_db` work
import os
import sys
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import subprocess
import pathlib
import sys

import code_db

mod = "TestInternalDeps"
helper_code = "add_one(x) = x + 1"
main_code = "use_add_one(x) = add_one(x) * 2"

print("Creating functions in DB...")
helper_id = code_db.add_function("add_one", "add one", helper_code, modules=[mod], tags=["julia", "generated"])
main_id = code_db.add_function("use_add_one", "use add_one", main_code, modules=[mod], tags=["julia", "generated"])

print(f"Helper ID: {helper_id}\nMain ID: {main_id}")
print("Adding dependency main -> helper in DB...")
code_db.add_dependency(main_id, helper_id)

print("Recorded dependencies for main:", code_db.list_dependencies(main_id))

# Generate module file
module_path = os.path.abspath(os.path.join("tests", "test_internal_deps_mod.jl"))
code_db.generate_module_file(mod, module_path, with_tests=False)
print(f"Generated module file at: {module_path}")

# Write Julia runner
runner_path = os.path.abspath(os.path.join("tests", "run_internal_deps.jl"))
# Convert backslashes to forward slashes for Julia include compatibility
module_path_unix = module_path.replace("\\", "/")
with open(runner_path, "w", encoding="utf-8") as f:
    f.write(f'include("{module_path_unix}")\n')
    f.write(f'println({mod}.use_add_one(3))\n')

print(f"Running Julia script: {runner_path}")
try:
    proc = subprocess.run(["julia", runner_path], capture_output=True, text=True)
    print("Return code:", proc.returncode)
    print("stdout:\n", proc.stdout)
    print("stderr:\n", proc.stderr)
except FileNotFoundError:
    print("Julia executable not found in PATH. Skipping execution. Module file created for inspection.")

print("Done.")
