#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2016 Adrian Perez <aperez@igalia.com>
#
# Distributed under terms of the GPLv3 license.
from os import environ, path as P
import sys
from revolt import main


def adjust_import_path():
    devel = environ.get("__REVOLT_DEVELOPMENT")
    if devel and devel.strip():
        # Prepend source directory path.
        sys.path.insert(0, P.dirname(P.dirname(__file__)))
    else:
        sys.path.insert(0, P.join(P.dirname(P.dirname(__file__)),
                                  "share", "revolt", "py"))


if __name__ == "__main__":
    #adjust_import_path()
    main(__file__)
