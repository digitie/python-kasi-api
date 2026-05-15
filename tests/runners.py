from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from kasi.parser import available_function_names, parse_function_response
from kasi.processor import process_function_result

RUNNERS: dict[str, dict[str, Callable[..., Any]]] = {
    name: {
        "parse": partial(parse_function_response, name),
        "process": partial(process_function_result, name),
    }
    for name in available_function_names()
}
