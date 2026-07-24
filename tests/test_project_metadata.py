from pathlib import Path
import tomllib


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_matches_the_supported_python_versions():
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)["project"]

    assert project["requires-python"] == ">=3.11"
    assert not any(
        dependency.startswith("importlib-metadata")
        for dependency in project["dependencies"]
    )
