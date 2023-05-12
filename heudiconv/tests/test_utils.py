from __future__ import annotations

from datetime import datetime
import json
from json.decoder import JSONDecodeError
import os
import os.path as op
from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

import pytest

from heudiconv.utils import (
    create_tree,
    get_datetime,
    get_heuristic_description,
    get_known_heuristics_with_descriptions,
    json_dumps_pretty,
    load_heuristic,
    load_json,
    remove_prefix,
    remove_suffix,
    save_json,
    strptime_micr,
    update_json,
)

from .utils import HEURISTICS_PATH


def test_get_known_heuristics_with_descriptions() -> None:
    d = get_known_heuristics_with_descriptions()
    assert {"reproin", "convertall"}.issubset(d)
    # ATM we include all, not only those two
    assert len(d) > 2
    assert len(d["reproin"]) > 50  # it has a good one
    assert len(d["reproin"].split(os.sep)) == 1  # but just one line


def test_get_heuristic_description() -> None:
    desc = get_heuristic_description("reproin", full=True)
    assert len(desc) > 1000
    # and we describe such details as
    assert "_ses-" in desc
    assert "_run-" in desc
    # and mention ReproNim ;)
    assert "ReproNim" in desc


def test_load_heuristic() -> None:
    by_name = load_heuristic("reproin")
    from_file = load_heuristic(op.join(HEURISTICS_PATH, "reproin.py"))

    assert by_name
    assert by_name.filename == from_file.filename

    with pytest.raises(ImportError):
        load_heuristic("unknownsomething")

    with pytest.raises(ImportError):
        load_heuristic(op.join(HEURISTICS_PATH, "unknownsomething.py"))


def test_json_dumps_pretty() -> None:
    pretty = json_dumps_pretty
    assert (
        pretty({"SeriesDescription": "Trace:Nov 13 2017 14-36-14 EST"})
        == '{\n  "SeriesDescription": "Trace:Nov 13 2017 14-36-14 EST"\n}'
    )
    assert pretty({}) == "{}"
    assert (
        pretty({"a": -1, "b": "123", "c": [1, 2, 3], "d": ["1.0", "2.0"]})
        == '{\n  "a": -1,\n  "b": "123",\n  "c": [1, 2, 3],\n  "d": ["1.0", "2.0"]\n}'
    )
    assert (
        pretty({"a": ["0.3", "-1.9128906358217845e-12", "0.2"]})
        == '{\n  "a": ["0.3", "-1.9128906358217845e-12", "0.2"]\n}'
    )
    # original, longer string
    tstr = (
        "f9a7d4be-a7d7-47d2-9de0-b21e9cd10755||"
        "Sequence: ve11b/master r/50434d5; "
        "Mar  3 2017 10:46:13 by eja"
    )
    # just the date which reveals the issue
    # tstr = 'Mar  3 2017 10:46:13 by eja'
    assert pretty({"WipMemBlock": tstr}) == '{\n  "WipMemBlock": "%s"\n}' % tstr


def test_load_json(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # test invalid json
    ifname = "invalid.json"
    invalid_json_file = str(tmp_path / ifname)
    create_tree(str(tmp_path), {ifname: "I'm Jason Bourne"})

    with pytest.raises(JSONDecodeError):
        load_json(str(invalid_json_file))

    # and even if we ask to retry a few times -- should be the same
    with pytest.raises(JSONDecodeError):
        load_json(str(invalid_json_file), retry=3)

    with pytest.raises(FileNotFoundError):
        load_json("absent123not.there", retry=3)

    assert ifname in caplog.text

    # test valid json
    vcontent = {"secret": "spy"}
    vfname = "valid.json"
    valid_json_file = str(tmp_path / vfname)
    save_json(valid_json_file, vcontent)

    assert load_json(valid_json_file) == vcontent

    calls = [0]
    json_load = json.load

    def json_load_patched(fp: IO[str]) -> Any:
        calls[0] += 1
        if calls[0] == 1:
            # just reuse bad file
            load_json(str(invalid_json_file))
        elif calls[0] == 2:
            raise FileNotFoundError()
        else:
            return json_load(fp)

    with patch.object(json, "load", json_load_patched):
        assert load_json(valid_json_file, retry=3) == vcontent


def test_update_json(tmp_path: Path) -> None:
    """
    Test utils.update_json()
    """
    dummy_json_file = str(tmp_path / "dummy.json")
    some_content = {"name": "Jason", "age": 30, "city": "New York"}
    save_json(dummy_json_file, some_content, pretty=True)

    added_content = {
        "LastName": "Bourne",
        "Movies": [
            "The Bourne Identity",
            "The Bourne Supremacy",
            "The Bourne Ultimatum",
            "The Bourne Legacy",
            "Jason Bourne",
        ],
    }
    update_json(dummy_json_file, added_content)

    # check that it was added:
    with open(dummy_json_file) as f:
        data = json.load(f)
    some_content.update(added_content)
    assert data == some_content


def test_get_datetime() -> None:
    """
    Test utils.get_datetime()
    """
    assert get_datetime("20200512", "162130") == "2020-05-12T16:21:30"
    assert get_datetime("20200512", "162130.5") == "2020-05-12T16:21:30.500000"
    assert (
        get_datetime("20200512", "162130.5", microseconds=False)
        == "2020-05-12T16:21:30"
    )


@pytest.mark.parametrize(
    "dt, fmt",
    [
        ("20230310190100", "%Y%m%d%H%M%S"),
        ("2023-04-02T11:47:09", "%Y-%m-%dT%H:%M:%S"),
    ],
)
def test_strptime_micr(dt: str, fmt: str) -> None:
    target = datetime.strptime(dt, fmt)
    assert strptime_micr(dt, fmt) == target
    assert strptime_micr(dt, fmt + "[.%f]") == target
    assert strptime_micr(dt + ".0", fmt + "[.%f]") == target
    assert strptime_micr(dt + ".000000", fmt + "[.%f]") == target
    assert strptime_micr(dt + ".1", fmt + "[.%f]") == datetime.strptime(
        dt + ".1", fmt + ".%f"
    )


def test_remove_suffix() -> None:
    """
    Test utils.remove_suffix()
    """
    s = "jason.bourne"
    assert remove_suffix(s, "") == s
    assert remove_suffix(s, "foo") == s
    assert remove_suffix(s, ".bourne") == "jason"


def test_remove_prefix() -> None:
    """
    Test utils.remove_prefix()
    """
    s = "jason.bourne"
    assert remove_prefix(s, "") == s
    assert remove_prefix(s, "foo") == s
    assert remove_prefix(s, "jason") == ".bourne"
