import math

from typing import Any, Callable, Dict, List, Optional

from nicegui import ui


# same order as quasar's client-side sort: empty values first, then numbers, then text
def sort_key(value: Any) -> tuple:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return (0, 0, "")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (1, value, "")

    return (2, 0, str(value).lower())

# ui.table that keeps every row on the server and only sends the page being shown
# nicegui sends the whole table to the browser again on every selection and page change,
# which was megabytes per click for big searches
# with "rowsNumber" in the pagination, quasar switches to server-side mode and asks for
# each page (and sort order) through a "request" event instead
class PagedTable(ui.table):
    def __init__(self,
                 *,
                 rows: List[Dict],
                 columns: List[Dict],
                 rows_per_page: int = 100,
                 page: int = 1,
                 on_page_change: Optional[Callable[[int], Any]] = None,
                 **kwargs: Any,
                ) -> None:

        super().__init__(
            rows = [],
            columns = columns,
            pagination = {"rowsPerPage": rows_per_page, "page": page, "sortBy": None, "descending": False, "rowsNumber": len(rows)},
            **kwargs,
        )

        self.all_rows = rows
        self._sort_fields = {column["name"]: column["field"] for column in columns}
        self._page_change_handler = on_page_change

        self.on("request", lambda e: self.show_page(e.args["pagination"]))
        self.show_page(self.pagination)

    # sort all rows, then send only the requested page
    def show_page(self, pagination: Dict) -> None:
        rows = self.all_rows

        sort_by = pagination.get("sortBy")
        if sort_by:
            field = self._sort_fields.get(sort_by, sort_by)
            rows = sorted(rows, key = lambda row: sort_key(row.get(field)), reverse = bool(pagination.get("descending")))

        # 0 rows per page is quasar's "All"
        rows_per_page = pagination.get("rowsPerPage") or max(len(rows), 1)
        last_page = max(math.ceil(len(rows) / rows_per_page), 1)
        page = min(max(pagination.get("page") or 1, 1), last_page)

        start = (page - 1) * rows_per_page
        self.rows = rows[start:start + rows_per_page]
        self.pagination = {**pagination, "page": page, "rowsNumber": len(rows)}

        if self._page_change_handler:
            self._page_change_handler(page)

        return None
