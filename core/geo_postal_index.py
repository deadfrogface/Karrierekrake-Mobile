"""Postal codes and place names of one country, read from the local GeoNames file.

The table is a plain CSV (see ``GeoDatasetManager._tsv_to_pgeocode_csv`` for the columns). It is read with the
standard library: no pandas, no pgeocode, and no code in here that can open a network connection. A missing
or unreadable file is an error for the caller; nothing is ever fetched to replace it.

Results are the ones the earlier pgeocode-based lookup gave:

* a postal code resolves to the mean of the coordinates of all its rows, and its place name is the names of
  those rows joined by ``", "`` in file order;
* a place name matches rows whose name is equal to it after ``str.casefold``.
"""
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass

_COLUMNS = ("postal_code", "place_name", "latitude", "longitude")
# Cells that mean "no value", as in the table reader used before (a place called "Null" stays unnamed).
_NO_VALUE = frozenset({
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A",
    "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
})


@dataclass(frozen=True)
class PostalRow:
    """Answer for one postal code. ``latitude`` and ``longitude`` are NaN when the code is unknown."""

    latitude: float
    longitude: float
    place_name: str


_UNKNOWN = PostalRow(math.nan, math.nan, "")


def _number(cell: str) -> float | None:
    if cell in _NO_VALUE:
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _mean(values: list[float]) -> float:
    return math.fsum(values) / len(values) if values else math.nan


class PostalIndex:
    """Lookup by postal code and by exact place name for one country file.

    Reading keeps the cells as text; numbers and the per-code answer are made on the first lookup of that code. The
    app preloads five countries at startup (about 30,000 codes) and then asks for a handful, so building every
    answer up front was most of the startup work in the background thread that competes with the window.
    """

    def __init__(self, rows: list[tuple[str, str, float | None, float | None]], data_path: str = "") -> None:
        """``rows`` are ``(postal_code, place_name, latitude, longitude)`` in file order."""
        self._data_path = data_path
        self._by_code: dict[str, list[tuple[str, object, object]]] = {}
        self._places: dict[str, list[tuple[str, object, object]]] = {}
        self._postal: dict[str, PostalRow] = {}
        for code, name, lat, lon in rows:
            self._add(code, name, lat, lon)
        self._folded_names: tuple[str, ...] | None = None

    def _add(self, code: str, name: str, lat: object, lon: object) -> None:
        entry = (name, lat, lon)
        group = self._by_code.get(code)
        if group is None:
            self._by_code[code] = [entry]
        else:
            group.append(entry)
        folded = name.casefold()
        same = self._places.get(folded)
        if same is None:
            self._places[folded] = [entry]
        else:
            same.append(entry)

    @staticmethod
    def _value(cell: object) -> float | None:
        return _number(cell) if isinstance(cell, str) else cell  # type: ignore[return-value]

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "PostalIndex":
        """Read one country file. Raises ``OSError`` or ``ValueError`` when it cannot be used."""
        data_path = os.fspath(path)
        index = cls([], data_path)
        add = index._add
        with open(data_path, encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                raise ValueError("empty postal table")
            try:
                code_at, name_at, lat_at, lon_at = (header.index(column) for column in _COLUMNS)
            except ValueError as exc:
                raise ValueError("postal table without the expected columns") from exc
            width = max(code_at, name_at, lat_at, lon_at) + 1
            for cells in reader:
                if len(cells) < width:
                    continue
                code = cells[code_at]
                if code in _NO_VALUE:
                    continue
                name = cells[name_at]
                add(code, "nan" if name in _NO_VALUE else name, cells[lat_at], cells[lon_at])
        return index

    def query_postal_code(self, code: str) -> PostalRow:
        key = str(code or "").strip().upper()
        hit = self._postal.get(key)
        if hit is not None:
            return hit
        group = self._by_code.get(key)
        if not group:
            return _UNKNOWN
        value = self._value
        lats = [lat for lat in (value(entry[1]) for entry in group) if lat is not None]
        lons = [lon for lon in (value(entry[2]) for entry in group) if lon is not None]
        row = PostalRow(_mean(lats), _mean(lons), ", ".join(name for name, _a, _b in group))
        self._postal[key] = row
        return row

    def exact_places(self, folded_name: str) -> list[tuple[str, float | None, float | None]]:
        """Rows ``(place_name, latitude, longitude)`` whose casefolded name equals ``folded_name``."""
        value = self._value
        return [(name, value(lat), value(lon)) for name, lat, lon in self._places.get(folded_name, ())]

    def names_containing(self, folded_part: str) -> set[str]:
        """Distinct casefolded place names that contain ``folded_part``."""
        names = self._folded_names
        if names is None:
            names = self._folded_names = tuple(self._places)
        return {name for name in names if name and folded_part in name}
