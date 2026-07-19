import csv
from io import StringIO


def csv_head(values: tuple[object, ...]) -> str:
    return csv_row(values)


def csv_row(values: tuple[object, ...]) -> str:
    output = StringIO()
    csv.writer(output, lineterminator="").writerow(
        "" if value is None else str(value) for value in values
    )
    return output.getvalue()
