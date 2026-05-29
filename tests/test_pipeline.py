"""Unit tests for pipeline_runner."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from pipeline_runner.config import PipelineConfig, Stage, Command
from pipeline_runner.parser import PipelineParser
from pipeline_runner.runner import PipelineRunner
from pipeline_runner.logger import PipelineLogger


# ─── Config Tests ───

def test_command_creation():
    cmd = Command(shell="echo hello", label="Greet")
    assert cmd.shell == "echo hello"
    assert cmd.label == "Greet"
    assert cmd.retry == 0


def test_stage_creation():
    stage = Stage(name="build", commands=[Command(shell="make")])
    assert stage.name == "build"
    assert stage.depends_on == []
    assert stage.parallel is False
    assert stage.retry == 0


def test_pipeline_config_defaults():
    cfg = PipelineConfig(name="Test", stages=[])
    assert cfg.env == {}
    assert cfg.on == "push"
    assert cfg.max_parallel == 3


# ─── Parser Tests ───

def test_parse_minimal_pipeline():
    yaml = """
name: CI
stages:
  - name: build
    commands:
      - shell: make
"""
    cfg = PipelineParser.parse_string(yaml)
    assert cfg.name == "CI"
    assert len(cfg.stages) == 1
    assert cfg.stages[0].name == "build"
    assert cfg.stages[0].commands[0].shell == "make"


def test_parse_full_pipeline():
    yaml = """
name: Full CI
on: push
env:
  APP: test
max_parallel: 5
stages:
  - name: lint
    commands:
      - shell: eslint .
        label: Lint
  - name: test
    depends_on: [lint]
    parallel: true
    retry: 3
    commands:
      - shell: pytest
        label: Tests
    env:
      NODE_ENV: test
"""
    cfg = PipelineParser.parse_string(yaml)
    assert cfg.on == "push"
    assert cfg.env["APP"] == "test"
    assert cfg.max_parallel == 5

    lint = cfg.stages[0]
    assert lint.commands[0].label == "Lint"

    test_stage = cfg.stages[1]
    assert test_stage.depends_on == ["lint"]
    assert test_stage.parallel is True
    assert test_stage.retry == 3
    assert test_stage.env["NODE_ENV"] == "test"


def test_parse_validation_rejects_empty_name():
    yaml = """
name: ""
stages: []
"""
    with pytest.raises(Exception):
        PipelineParser.parse_string(yaml)


def test_parse_validation_rejects_no_stages():
    yaml = """
name: Bad
stages: []
"""
    with pytest.raises(Exception):
        PipelineParser.parse_string(yaml)


def test_parse_validation_rejects_no_commands():
    yaml = """
name: Bad
stages:
  - name: build
"""
    with pytest.raises(Exception):
        PipelineParser.parse_string(yaml)


def test_parse_file(tmp_path):
    p = tmp_path / "pipeline.yml"
    p.write_text("name: File\nstages:\n  - name: build\n    commands:\n      - shell: echo hi\n")
    cfg = PipelineParser.parse_file(str(p))
    assert cfg.name == "File"


def test_parse_file_not_found():
    with pytest.raises(SystemExit):
        PipelineParser.parse_file("/nonexistent/pipeline.yml")


def test_validate_dry_run():
    yaml = """
name: DryRun
stages:
  - name: step1
    commands:
      - shell: echo 1
"""
    result = PipelineParser.validate(yaml)
    assert result["valid"] is True
    assert result["stages"] == 1
    assert result["commands"] == 1
    assert result["has_cycle"] is False


# ─── Logger Tests ───

def test_logger_creates_log_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PipelineLogger(log_dir=tmpdir, stage="test")
        logger.info("hello")
        logger.success("done")
        logger.error("fail")
        # Check log file was created
        log_files = list(Path(tmpdir).glob("*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "hello" in content
        assert "DONE" in content
        assert "FAIL" in content


# ─── Runner Tests ───

def _make_runner(yaml: str, *, approve_all=False, log_dir=None) -> PipelineRunner:
    cfg = PipelineParser.parse_string(yaml)
    approvals = {}
    if approve_all:
        approvals = {s.name: True for s in cfg.stages if s.requires_approval}
    return PipelineRunner(cfg, approvals=approvals, log_dir=log_dir)


@pytest.mark.asyncio
async def test_runner_simple_pipeline():
    yaml = """
name: Simple
stages:
  - name: build
    commands:
      - shell: echo "hello from step 1"
        label: Step 1
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "completed"
    assert result["stages_total"] == 1
    assert result["stages_completed"] == 1


@pytest.mark.asyncio
async def test_runner_dependency_order():
    yaml = """
name: Order
stages:
  - name: first
    commands:
      - shell: echo first
  - name: second
    depends_on: [first]
    commands:
      - shell: echo second
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "completed"
    assert result["stages_completed"] == 2


@pytest.mark.asyncio
async def test_runner_approval_blocks():
    yaml = """
name: Approval
stages:
  - name: deploy
    requires_approval: true
    commands:
      - shell: echo deploy
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "blocked"
    assert len(runner.pending_approvals) == 1


@pytest.mark.asyncio
async def test_runner_approval_approved():
    yaml = """
name: Approved
stages:
  - name: deploy
    requires_approval: true
    commands:
      - shell: echo deploy
"""
    runner = _make_runner(yaml, approve_all=True, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_runner_retry_on_failure():
    yaml = """
name: Retry
stages:
  - name: flaky
    retry: 2
    commands:
      - shell: echo "flaky test"
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_runner_cyclic_dependency():
    yaml = """
name: Cycle
stages:
  - name: a
    depends_on: [b]
    commands:
      - shell: echo a
  - name: b
    depends_on: [a]
    commands:
      - shell: echo b
"""
    runner = _make_runner(yaml)
    result = await runner.run()
    assert result["status"] == "failed"
    assert "cycle" in result["error"].lower()


@pytest.mark.asyncio
async def test_runner_parallel_stages():
    yaml = """
name: Parallel
stages:
  - name: a
    commands:
      - shell: echo a
  - name: b
    commands:
      - shell: echo b
  - name: c
    depends_on: [a, b]
    commands:
      - shell: echo c
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    result = await runner.run()
    assert result["status"] == "completed"
    assert result["stages_completed"] == 3


@pytest.mark.asyncio
async def test_runner_status_tracking():
    yaml = """
name: Status
stages:
  - name: build
    commands:
      - shell: echo building
  - name: test
    commands:
      - shell: echo testing
"""
    runner = _make_runner(yaml, log_dir=tempfile.mkdtemp())
    # Before run
    status = runner.get_status()
    assert status["pipeline_name"] == "Status"
    assert status["stages_total"] == 2

    result = await runner.run()
    assert result["duration"] > 0
