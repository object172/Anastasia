# -*- coding: utf-8 -*-
import contextlib
import inspect
import os


__all__ = ('up_import', )


CURRENT_DIR = os.path.dirname(
    os.path.abspath(
        inspect.getfile(inspect.currentframe())
    )
)


@contextlib.contextmanager
def up_import(level_up=1):
    up_dir = CURRENT_DIR
    for i in xrange(level_up):
        up_dir = os.path.dirname(up_dir)

    if not os.sys.path or up_dir != os.sys.path[0]:
        is_up_import = True
        os.sys.path.insert(0, up_dir)
    else:
        is_up_import = False

    try:
        yield
    finally:
        if is_up_import:
            os.sys.path.remove(up_dir)

if __name__ == '__main__':
    import unittest

    class Test(unittest.TestCase):
        def test_up_import(self):
            start_pypath = os.sys.path[:]

            with up_import():
                pypath1 = os.sys.path[:]
                with up_import():
                    pypath2 = os.sys.path[:]

            with up_import(0):
                pypath3 = os.sys.path[:]

            end_pypath = os.sys.path[:]

            self.assertEqual(start_pypath, end_pypath)
            self.assertEqual(pypath1, pypath2)
            self.assertEqual(start_pypath, pypath3)

            self.assertEqual(len(start_pypath) + 1, len(pypath1))

    unittest.main()
