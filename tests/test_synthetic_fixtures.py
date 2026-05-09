import json

from tests.fixtures.synthetic_manga import generate_synthetic_manga_fixture


def test_synthetic_manga_fixture_generation_is_deterministic(tmp_path):
    first = generate_synthetic_manga_fixture(tmp_path / "first")
    second = generate_synthetic_manga_fixture(tmp_path / "second")

    assert [page["story_page"] for page in first["pages"]] == [1, 2, 3]
    assert [page["visible_page_number"] for page in first["pages"]] == [99, 7, 42]
    assert first["expected_summary_points"][-1] == (
        "Small corner page markings 99, 7, and 42 are not story order."
    )

    first_images = [path.read_bytes() for path in (tmp_path / "first").glob("*.png")]
    second_images = [path.read_bytes() for path in (tmp_path / "second").glob("*.png")]
    assert len(first_images) == 3
    assert first_images == second_images
    assert first_images[0].startswith(b"\x89PNG\r\n\x1a\n")

    reference = json.loads((tmp_path / "first" / "reference.json").read_text(encoding="utf-8"))
    assert reference["title"] == "Synthetic Key Quest"
    assert reference["pages"][0]["dialogue"] == ["RIA: A KEY!", "KAI: HIDE IT!"]
