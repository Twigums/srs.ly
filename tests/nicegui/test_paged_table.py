import math

from src.nicegui.paged_table import PagedTable, sort_key


# ---------------------------------------------------------------------------
# PagedTable — only the visible page of a search is sent to the browser
# ---------------------------------------------------------------------------

COLUMNS = [
    {"name": "kanji", "label": "Kanji", "field": "Kanji"},
    {"name": "grade", "label": "Grade", "field": "Grade", "sortable": True},
]


def _rows(n):
    return [{"id": i, "Kanji": f"k{i}", "Grade": i % 9} for i in range(n)]


def _send_request(table, pagination):
    """Simulate the browser's "request" event (page change or sort click)."""
    listener = next(l for l in table._event_listeners.values() if l.type == "request")
    table._handle_event({"listener_id": listener.id, "args": {"pagination": pagination, "filter": None}})


class TestPagedTable:
    def test_only_the_first_page_is_sent(self):
        table = PagedTable(rows = _rows(250), columns = COLUMNS)

        assert [row["id"] for row in table.rows] == list(range(100))
        assert table.pagination["page"] == 1
        assert table.pagination["rowsNumber"] == 250

    def test_request_event_sends_that_page(self):
        table = PagedTable(rows = _rows(250), columns = COLUMNS)

        _send_request(table, {**table.pagination, "page": 3})

        assert [row["id"] for row in table.rows] == list(range(200, 250))
        assert table.pagination["page"] == 3

    def test_page_past_the_end_is_clamped(self):
        pages = []
        table = PagedTable(rows = _rows(250), columns = COLUMNS, page = 7, on_page_change = pages.append)

        assert table.pagination["page"] == 3
        assert pages == [3]

    def test_sorting_covers_every_row_not_just_the_page(self):
        rows = _rows(250)
        table = PagedTable(rows = rows, columns = COLUMNS)

        _send_request(table, {**table.pagination, "sortBy": "grade", "descending": True})

        expected = sorted((row["Grade"] for row in rows), reverse = True)[:100]
        assert [row["Grade"] for row in table.rows] == expected
        assert table.pagination["sortBy"] == "grade"

    def test_all_rows_per_page_sends_everything(self):
        table = PagedTable(rows = _rows(250), columns = COLUMNS)

        table.show_page({**table.pagination, "rowsPerPage": 0})

        assert len(table.rows) == 250
        assert table.pagination["rowsPerPage"] == 0

    def test_no_rows(self):
        table = PagedTable(rows = [], columns = COLUMNS)

        assert table.rows == []
        assert table.pagination["page"] == 1


class TestSortKey:
    def test_empty_values_then_numbers_then_text(self):
        ordered = sorted(["b", 10, None, "A", 2, float("nan")], key = sort_key)

        assert ordered[0] is None and math.isnan(ordered[1])
        assert ordered[2:] == [2, 10, "A", "b"]
