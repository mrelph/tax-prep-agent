"""Tests for the self-update module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tax_agent.updater import (
    CLONE_DIR,
    UpdateResult,
    check_for_updates,
    get_install_type,
    get_repo_dir,
    perform_update,
)


class TestGetInstallType:
    """Tests for get_install_type()."""

    def test_pip_install_no_git(self, tmp_path):
        """When there's no .git directory, returns 'pip'."""
        # Mimic: <root>/src/tax_agent/updater.py with no .git at <root>
        (tmp_path / "src" / "tax_agent").mkdir(parents=True)
        fake_file = tmp_path / "src" / "tax_agent" / "updater.py"
        fake_file.touch()

        with patch("tax_agent.updater.__file__", str(fake_file)):
            result = get_install_type()
            assert result == "pip"

    def test_git_clone_install(self, tmp_path):
        """When .git exists and path matches CLONE_DIR, returns 'git-clone'."""
        # Create fake repo structure
        (tmp_path / ".git").mkdir()
        (tmp_path / "src" / "tax_agent").mkdir(parents=True)
        fake_file = tmp_path / "src" / "tax_agent" / "updater.py"
        fake_file.touch()

        with patch("tax_agent.updater.__file__", str(fake_file)):
            with patch("tax_agent.updater.CLONE_DIR", tmp_path):
                result = get_install_type()
                assert result == "git-clone"

    def test_editable_install(self, tmp_path):
        """When .git exists but path doesn't match CLONE_DIR, returns 'editable'."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "src" / "tax_agent").mkdir(parents=True)
        fake_file = tmp_path / "src" / "tax_agent" / "updater.py"
        fake_file.touch()

        with patch("tax_agent.updater.__file__", str(fake_file)):
            with patch("tax_agent.updater.CLONE_DIR", Path("/nonexistent")):
                result = get_install_type()
                assert result == "editable"


class TestGetRepoDir:
    """Tests for get_repo_dir()."""

    def test_returns_none_for_pip(self):
        with patch("tax_agent.updater.get_install_type", return_value="pip"):
            assert get_repo_dir() is None

    def test_returns_path_for_git_clone(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "src" / "tax_agent").mkdir(parents=True)
        fake_file = tmp_path / "src" / "tax_agent" / "updater.py"
        fake_file.touch()

        with patch("tax_agent.updater.get_install_type", return_value="git-clone"):
            with patch("tax_agent.updater.__file__", str(fake_file)):
                result = get_repo_dir()
                assert result == tmp_path


class TestCheckForUpdates:
    """Tests for check_for_updates()."""

    def test_no_repo_returns_error(self):
        with patch("tax_agent.updater.get_repo_dir", return_value=None):
            result = check_for_updates()
            assert result.error
            assert "not installed from a git repository" in result.error.lower()

    def test_up_to_date(self, tmp_path):
        """When local and remote refs match, updated=False."""
        def fake_run_git(*args, cwd):
            mock = MagicMock(spec=subprocess.CompletedProcess)
            mock.returncode = 0
            if args[0] == "rev-parse" and "HEAD" in args:
                mock.stdout = "abc1234\n"
            elif args[0] == "fetch":
                mock.stdout = ""
                mock.stderr = ""
            elif args[0] == "rev-parse" and "origin/main" in args:
                mock.stdout = "abc1234\n"
            else:
                mock.stdout = ""
            mock.stderr = ""
            return mock

        with patch("tax_agent.updater.get_repo_dir", return_value=tmp_path):
            with patch("tax_agent.updater._run_git", side_effect=fake_run_git):
                result = check_for_updates()
                assert not result.updated
                assert result.old_ref == "abc1234"
                assert result.new_ref == "abc1234"
                assert not result.error

    def test_updates_available(self, tmp_path):
        """When refs differ, returns updated=True with commit summary."""
        def fake_run_git(*args, cwd):
            mock = MagicMock(spec=subprocess.CompletedProcess)
            mock.returncode = 0
            mock.stderr = ""
            if args[0] == "rev-parse" and "HEAD" in args:
                mock.stdout = "abc1234\n"
            elif args[0] == "fetch":
                mock.stdout = ""
            elif args[0] == "rev-parse" and "origin/main" in args:
                mock.stdout = "def5678\n"
            elif args[0] == "log":
                mock.stdout = "def5678 fix: resolve parsing bug\naaa1111 feat: add new analyzer\n"
            else:
                mock.stdout = ""
            return mock

        with patch("tax_agent.updater.get_repo_dir", return_value=tmp_path):
            with patch("tax_agent.updater._run_git", side_effect=fake_run_git):
                result = check_for_updates()
                assert result.updated
                assert result.old_ref == "abc1234"
                assert result.new_ref == "def5678"
                assert len(result.commit_summary) == 2
                assert not result.error

    def test_fetch_failure(self, tmp_path):
        """When git fetch fails, returns error."""
        call_count = 0

        def fake_run_git(*args, cwd):
            nonlocal call_count
            call_count += 1
            mock = MagicMock(spec=subprocess.CompletedProcess)
            mock.stderr = ""
            if args[0] == "rev-parse" and "HEAD" in args:
                mock.returncode = 0
                mock.stdout = "abc1234\n"
            elif args[0] == "fetch":
                mock.returncode = 1
                mock.stdout = ""
                mock.stderr = "fatal: unable to access"
            else:
                mock.returncode = 0
                mock.stdout = ""
            return mock

        with patch("tax_agent.updater.get_repo_dir", return_value=tmp_path):
            with patch("tax_agent.updater._run_git", side_effect=fake_run_git):
                result = check_for_updates()
                assert result.error
                assert "fetch" in result.error.lower()


class TestPerformUpdate:
    """Tests for perform_update()."""

    def test_no_repo_returns_error(self):
        with patch("tax_agent.updater.get_repo_dir", return_value=None):
            result = perform_update()
            assert result.error
            assert "not installed from a git repository" in result.error.lower()

    def test_up_to_date_skips_pull(self, tmp_path):
        """When already up to date, no pull or pip install happens."""
        with patch("tax_agent.updater.get_repo_dir", return_value=tmp_path):
            with patch("tax_agent.updater.check_for_updates") as mock_check:
                mock_check.return_value = UpdateResult(updated=False, old_ref="abc1234", new_ref="abc1234")
                result = perform_update()
                assert not result.updated
                assert not result.error

    def test_successful_update(self, tmp_path):
        """When updates are available, pulls and pip installs."""
        check_result = UpdateResult(
            updated=True,
            old_ref="abc1234",
            new_ref="def5678",
            commit_summary=["def5678 fix something"],
        )

        def fake_run_git(*args, cwd):
            mock = MagicMock(spec=subprocess.CompletedProcess)
            mock.returncode = 0
            mock.stdout = ""
            mock.stderr = ""
            return mock

        fake_pip = MagicMock(spec=subprocess.CompletedProcess)
        fake_pip.returncode = 0
        fake_pip.stdout = ""
        fake_pip.stderr = ""

        with patch("tax_agent.updater.get_repo_dir", return_value=tmp_path):
            with patch("tax_agent.updater.check_for_updates", return_value=check_result):
                with patch("tax_agent.updater._run_git", side_effect=fake_run_git):
                    with patch("subprocess.run", return_value=fake_pip) as mock_sub_run:
                        result = perform_update()
                        assert result.updated
                        assert result.old_ref == "abc1234"
                        assert result.new_ref == "def5678"
                        # Verify pip install was called
                        mock_sub_run.assert_called_once()
                        pip_args = mock_sub_run.call_args[0][0]
                        assert "-m" in pip_args
                        assert "pip" in pip_args
