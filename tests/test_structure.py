from pathlib import Path


def test_deploy_layout():
    root = Path(__file__).resolve().parents[1]
    assert (root / "app.py").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "radar" / "engine.py").is_file()
    assert (root / "radar" / "crawler.py").is_file()
    assert (root / "radar" / "discovery.py").is_file()
    req = (root / "requirements.txt").read_text()
    assert "crawlee" in req and "extruct" in req and "-e ." in req
