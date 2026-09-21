#!/usr/bin/env python3
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class BackupRecoveryContract(unittest.TestCase):
    def test_restore_verifies_before_any_destructive_docker_command(self):
        source = (ROOT / "scripts/restore.sh").read_text()
        self.assertLess(source.index("SHA256SUMS"), source.index("docker compose stop"))
        self.assertLess(source.index("sha256sum -c"), source.index("docker compose stop"))

    def test_tampered_backup_is_rejected_before_docker_is_called(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = pathlib.Path(raw)
            (directory / "database.sql").write_text("database")
            (directory / "espocrm-data.tgz").write_text("archive")
            (directory / "git-commit.txt").write_text("commit")
            subprocess.run(
                "shasum -a 256 database.sql espocrm-data.tgz git-commit.txt > SHA256SUMS",
                cwd=directory, shell=True, check=True,
            )
            (directory / "database.sql").write_text("tampered")
            fake_bin = directory / "bin"
            fake_bin.mkdir()
            marker = directory / "docker-called"
            docker = fake_bin / "docker"
            docker.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 99\n")
            docker.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"
            result = subprocess.run(
                [str(ROOT / "scripts/restore.sh"), str(directory)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(marker.exists(), "integrity failure must happen before Docker")


if __name__ == "__main__":
    unittest.main()
