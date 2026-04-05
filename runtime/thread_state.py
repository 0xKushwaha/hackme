"""
Shared thread-local routing state.

Imported by server.py (which sets run_state on the pipeline thread) and
by any phase/module that spawns its own ThreadPoolExecutor workers — those
workers must inherit run_state from the parent thread so print() is routed
to the correct RunState and the frontend receives live log updates.
"""
import threading

_thread_local = threading.local()


def propagate_to_worker(fn, *args, **kwargs):
    """
    Wrap a callable so it inherits the calling thread's run_state.
    Use with ThreadPoolExecutor.submit():

        pool.submit(propagate_to_worker, my_fn, arg1, arg2)
    """
    state = getattr(_thread_local, "run_state", None)

    def _wrapper():
        _thread_local.run_state = state
        try:
            return fn(*args, **kwargs)
        finally:
            _thread_local.run_state = None

    return _wrapper
