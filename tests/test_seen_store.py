from home_agent import seen_store


def test_load_missing_file_returns_empty(tmp_path):
    assert seen_store.load(tmp_path / "missing.json") == {}


def test_mark_and_check_seen_round_trips(tmp_path):
    path = tmp_path / "seen.json"
    store = seen_store.load(path)
    assert not seen_store.is_seen(store, "abc:01")
    store = seen_store.mark_seen(path, store, "abc:01", "analysis-id-1")
    assert seen_store.is_seen(store, "abc:01")

    reloaded = seen_store.load(path)
    assert seen_store.is_seen(reloaded, "abc:01")
    assert reloaded["abc:01"]["analysis_id"] == "analysis-id-1"


def test_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("not json", encoding="utf-8")
    assert seen_store.load(path) == {}
