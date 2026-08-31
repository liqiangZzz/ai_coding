"""为 agent/backends/permissions.py 中的安全校验函数提供全面单元测试。

覆盖：
- normalize_safe_command: 白名单命令通过、shell 操作符拦截、危险关键词拦截
- assert_path_inside: 工作区内路径通过、越界路径被拒绝
"""

import tempfile
import unittest
from pathlib import Path

from agent.backends.permissions import WorkspacePermissionError, assert_path_inside, normalize_safe_command


# ── normalize_safe_command 测试 ──────────────────────────────────────────────

class TestNormalizeSafeCommand(unittest.TestCase):
    """normalize_safe_command 的单元测试。"""

    # ── 白名单命令通过 ───────────────────────────────────────────

    def test_allows_git_status(self) -> None:
        self.assertEqual(normalize_safe_command("git status"), "git status")

    def test_allows_git_clone(self) -> None:
        self.assertEqual(
            normalize_safe_command("git clone https://github.com/foo/bar.git"),
            "git clone https://github.com/foo/bar.git",
        )

    def test_allows_python_exec(self) -> None:
        self.assertEqual(normalize_safe_command("python -m pytest tests/"), "python -m pytest tests/")

    def test_allows_python3(self) -> None:
        self.assertEqual(normalize_safe_command("python3 --version"), "python3 --version")

    def test_allows_pip_install(self) -> None:
        self.assertEqual(normalize_safe_command("pip install requests"), "pip install requests")

    def test_allows_pytest(self) -> None:
        self.assertEqual(normalize_safe_command("pytest tests/ -v"), "pytest tests/ -v")

    def test_allows_ls(self) -> None:
        self.assertEqual(normalize_safe_command("ls /projects/ai_coding"), "ls /projects/ai_coding")

    def test_allows_cat(self) -> None:
        self.assertEqual(normalize_safe_command("cat README.md"), "cat README.md")

    def test_allows_pwd(self) -> None:
        self.assertEqual(normalize_safe_command("pwd"), "pwd")

    def test_allows_ruff(self) -> None:
        self.assertEqual(normalize_safe_command("ruff check agent/"), "ruff check agent/")

    def test_strips_trailing_tail_pipe(self) -> None:
        """尾部 | tail -5 应被剥离，其余部分通过。"""
        self.assertEqual(normalize_safe_command("git status | tail -5"), "git status")

    def test_strips_trailing_2and1(self) -> None:
        """尾部 2>&1 应被剥离，其余部分通过。"""
        self.assertEqual(normalize_safe_command("python script.py 2>&1"), "python script.py")

    # ── Shell 操作符拦截 ─────────────────────────────────────────

    def test_blocks_pipe_operator(self) -> None:
        """非尾部管道（如 | grep）应被拦截。"""
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("ls | grep foo")

    def test_blocks_redirect_gt(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("ls > /tmp/out.txt")

    def test_blocks_redirect_lt(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("cat < /etc/passwd")

    def test_blocks_double_ampersand(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("git status && rm -rf /")

    def test_blocks_double_pipe(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("ls || echo fail")

    def test_blocks_semicolon(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("ls; rm -rf /")

    def test_blocks_command_substitution(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("echo $(whoami)")

    def test_blocks_backtick(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("echo `whoami`")

    def test_blocks_newline_injection(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("ls\nrm -rf /")

    def test_blocks_single_ampersand(self) -> None:
        """单独的 & 用于后台运行也应被拦截。"""
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("sleep 10 &")

    # ── 危险关键词拦截 ──────────────────────────────────────────

    def test_blocks_rm_rf(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("rm -rf /")

    def test_blocks_shutdown(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("shutdown now")

    def test_blocks_format(self) -> None:
        with self.assertRaises(WorkspacePermissionError):
            normalize_safe_command("format C:")


# ── assert_path_inside 测试 ──────────────────────────────────────────────────

class TestAssertPathInside(unittest.TestCase):
    """assert_path_inside 的单元测试。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # ── 工作区内路径通过 ────────────────────────────────────────

    def test_allows_relative_subdir_path(self) -> None:
        """相对路径应在工作区内通过。"""
        result = assert_path_inside(self.root / "subdir/file.txt", self.root)
        self.assertEqual(result, self.root / "subdir/file.txt")

    def test_allows_root_path_itself(self) -> None:
        """根目录自身应通过。"""
        result = assert_path_inside(self.root, self.root)
        self.assertEqual(result, self.root)

    def test_allows_absolute_path_inside_workspace(self) -> None:
        """工作区内的绝对路径应通过。"""
        inner = self.root / "a/b/c.py"
        inner.mkdir(parents=True, exist_ok=True)
        result = assert_path_inside(inner, self.root)
        self.assertEqual(result, inner)

    def test_allows_normalized_path_with_dots_inside(self) -> None:
        """工作区内包含 . 的路径经 resolve 后仍应通过。"""
        path = self.root / "a/./b/foo.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        result = assert_path_inside(path, self.root)
        expected = self.root / "a/b/foo.py"
        self.assertEqual(result, expected)

    # ── 越界路径被拒绝 ──────────────────────────────────────────

    def test_blocks_dotdot_traversal(self) -> None:
        """../../ 越界路径应抛出 WorkspacePermissionError。"""
        with self.assertRaises(WorkspacePermissionError):
            assert_path_inside(self.root / "subdir/../../../etc/passwd", self.root)

    def test_blocks_absolute_path_outside(self) -> None:
        """指向工作区外的绝对路径应被拒绝。"""
        with self.assertRaises(WorkspacePermissionError):
            assert_path_inside(Path("/etc/passwd"), self.root)

    def test_blocks_root_parent_traversal(self) -> None:
        """从根目录 ../ 越界应被拒绝。"""
        with self.assertRaises(WorkspacePermissionError):
            assert_path_inside(self.root / "../outside", self.root)


if __name__ == "__main__":
    unittest.main()