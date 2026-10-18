"""Record a candidate type error that the frozen harness failed to catch.

An effects program called get() on a string. Python AttributeError escaped the
bounded evaluator. Adding it to the existing MALFORMED_PROGRAM error set records
failure; it does not make the program valid or change any successful execution.
This supplement leaves all frozen source files untouched.
"""
import runpy
import strict_state


def install():
    if AttributeError not in strict_state.ERRORS:
        strict_state.ERRORS = (*strict_state.ERRORS, AttributeError)


if __name__ == '__main__':
    install()
    runpy.run_path(str(strict_state.STUDY/'transport_recovery.py'),run_name='__main__')
