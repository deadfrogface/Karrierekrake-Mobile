from scripts.package_size_report import render, size_report


def test_size_report_groups_library_folders_and_sorts_files(tmp_path):
    root = tmp_path / "App"
    (root / "_internal" / "qt" / "plugins").mkdir(parents=True)
    (root / "_internal" / "qt" / "plugins" / "big.dll").write_bytes(b"x" * 3000)
    (root / "_internal" / "small.pyd").write_bytes(b"x" * 10)
    (root / "App.exe").write_bytes(b"x" * 500)

    report = size_report(root, top=5)

    assert report["total_bytes"] == 3510
    assert report["file_count"] == 3
    assert report["largest_files"][0] == {"path": "_internal/qt/plugins/big.dll", "bytes": 3000}
    folders = {item["path"]: item["bytes"] for item in report["largest_folders"]}
    assert folders["_internal/qt"] == 3000
    assert folders["_internal"] == 10
    assert folders["(top level)"] == 500
    assert "MiB" in render(report)
