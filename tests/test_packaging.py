"""Packaging, typing and portability checks that need no hardware.

- one version everywhere, and the MicroPython file list is complete;
- every module has a type stub with the same public names, plus py.typed;
- every module has an API reference page;
- the modules shipped to MicroPython import nothing CPython-only at module level.
"""

import ast
import contextlib
import importlib
import importlib.util
import io
import json
import os
import re
import sys
import unittest
from unittest import mock

import helpers

PKG = os.path.join(helpers.ROOT, "ups_hat")
PI_ONLY = {"cli", "pimon"}
MODULES = sorted(f[:-3] for f in os.listdir(PKG) if f.endswith(".py"))
MP_MODULE_IMPORTS = {"sys", "time", "json", "micropython"}   # all exist on MicroPython


def _tree(path):
    with open(path) as f:
        return ast.parse(f.read(), path)


def _public_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {n for n in names if not n.startswith("_")}


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(helpers.ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VersionTests(unittest.TestCase):
    def test_check_packaging_tool(self):
        tool = _load_tool("check_packaging")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(sys, "argv", ["check_packaging.py"]):
            self.assertEqual(tool.main(), 0, out.getvalue())

    def test_versions_agree(self):
        import ups_hat
        with open(os.path.join(helpers.ROOT, "pyproject.toml")) as f:
            py = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)
        with open(os.path.join(helpers.ROOT, "micropython", "package.json")) as f:
            mp = json.load(f)["version"]
        self.assertEqual({py, mp, ups_hat.__version__}, {ups_hat.__version__})
        self.assertRegex(ups_hat.__version__, r"^\d+\.\d+\.\d+$")

    def test_package_json_urls(self):
        with open(os.path.join(helpers.ROOT, "micropython", "package.json")) as f:
            pkg = json.load(f)
        self.assertEqual(pkg["deps"], [])
        for dest, src in pkg["urls"]:
            with self.subTest(dest=dest):
                self.assertTrue(src.startswith("github:PinGoblin/UPS_HAT/"))
                self.assertTrue(os.path.exists(os.path.join(helpers.ROOT, dest)))


class TypingTests(unittest.TestCase):
    def test_py_typed_marker(self):
        self.assertTrue(os.path.exists(os.path.join(PKG, "py.typed")))

    def test_every_module_has_a_matching_stub(self):
        for name in MODULES:
            with self.subTest(module=name):
                stub = os.path.join(PKG, name + ".pyi")
                self.assertTrue(os.path.exists(stub), "missing " + name + ".pyi")
                if name == "__init__":
                    continue
                missing = _public_names(_tree(os.path.join(PKG, name + ".py"))) - _public_names(_tree(stub))
                self.assertEqual(missing, set(), "public names missing from the stub")

    def test_package_exports_match_stub(self):
        import ups_hat
        stub = _tree(os.path.join(PKG, "__init__.pyi"))
        exported = set()
        for node in stub.body:
            if isinstance(node, ast.ImportFrom):
                exported.update(a.asname or a.name for a in node.names)
        for name in exported:
            with self.subTest(name=name):
                self.assertTrue(hasattr(ups_hat, name))


class DocsTests(unittest.TestCase):
    def test_every_module_has_a_reference_page(self):
        ref = os.path.join(helpers.ROOT, "docs", "api", "reference")
        pages = ""
        for f in os.listdir(ref):
            with open(os.path.join(ref, f)) as fh:
                pages += fh.read()
        for name in MODULES:
            if name.startswith("_"):
                continue
            with self.subTest(module=name):
                self.assertIn("::: ups_hat." + name, pages)

    def test_every_module_has_a_docstring(self):
        for name in MODULES:
            with self.subTest(module=name):
                self.assertTrue(ast.get_docstring(_tree(os.path.join(PKG, name + ".py"))))


class PortabilityTests(unittest.TestCase):
    """Modules that MicroPython installs must import cleanly there."""

    def test_module_level_imports(self):
        for name in MODULES:
            if name in PI_ONLY:
                continue
            tree = _tree(os.path.join(PKG, name + ".py"))
            nodes = list(tree.body)
            for node in tree.body:                    # include imports guarded by try/except
                if isinstance(node, ast.Try):
                    nodes += node.body + [h for hd in node.handlers for h in hd.body]
            imported = set()
            for node in nodes:
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=name):
                self.assertLessEqual(imported, MP_MODULE_IMPORTS)

    def test_no_cpython_only_syntax(self):
        """No walrus, match statements or type annotations in shipped modules (MicroPython 1.20+ safe)."""
        for name in MODULES:
            if name in PI_ONLY:
                continue
            tree = _tree(os.path.join(PKG, name + ".py"))
            with self.subTest(module=name):
                for node in ast.walk(tree):
                    self.assertNotIsInstance(node, ast.NamedExpr)
                    if hasattr(ast, "Match"):
                        self.assertNotIsInstance(node, ast.Match)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.assertIsNone(node.returns, "annotations belong in the .pyi stub")
                        for a in node.args.args + node.args.kwonlyargs:
                            self.assertIsNone(a.annotation, "annotations belong in the .pyi stub")

    def test_all_modules_import(self):
        for name in MODULES:
            with self.subTest(module=name):
                importlib.import_module("ups_hat" if name == "__init__" else "ups_hat." + name)


if __name__ == "__main__":
    unittest.main()
