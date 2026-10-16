import logging

ACCESS_LOGGER_NAME = "uvicorn.access"
REDACTED_QUERY = "?[redacted]"


class QueryStringRedactingFilter(logging.Filter):
    """Remove query strings from access log lines.

    Searches take the customer's latitude and longitude as query parameters,
    so an unfiltered access log would keep a record of where each customer
    was. The path and the fact that there was a query are kept; the values are not.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn logs each request with the arguments
        # (client address, method, path with query, HTTP version, status code).
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            path_with_query = record.args[2]
            if isinstance(path_with_query, str) and "?" in path_with_query:
                path = path_with_query.split("?", 1)[0]
                record.args = (*record.args[:2], path + REDACTED_QUERY, *record.args[3:])
        return True


def redact_query_strings_in_access_log() -> None:
    access_logger = logging.getLogger(ACCESS_LOGGER_NAME)
    if not any(isinstance(existing, QueryStringRedactingFilter) for existing in access_logger.filters):
        access_logger.addFilter(QueryStringRedactingFilter())
