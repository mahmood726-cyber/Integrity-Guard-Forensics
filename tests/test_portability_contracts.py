import json
from pathlib import Path, PurePath


def test_submission_config_is_repo_relative():
    config_path = Path(__file__).parent.parent / "e156-submission" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["title"].startswith("Integrity Guard Forensics:")
    assert config["type"] == "methods"
    assert not PurePath(config["path"]).is_absolute()
    assert config["path"] == ".."


def test_release_surface_has_no_local_machine_paths():
    repo_root = Path(__file__).parent.parent
    checked = [
        repo_root / "README.md",
        repo_root / "e156-submission" / "config.json",
    ]
    forbidden = (
        "C:\\Users\\user",
        "C:\\Integrity-Guard-Forensics",
        "OneDrive - NHS",
        "file:///C:/",
    )

    for path in checked:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path.name} leaked {marker}"
