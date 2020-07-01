"""
To use, create a SystemMutex, check if it was acquired (get_mutex_aquired()) and if acquired the
mutex is kept until the instance is collected or release_mutex is called.

I.e.:

    mutex = SystemMutex('my_unique_name')
    if mutex.get_mutex_aquired():
        print('acquired')
    else:
        print('not acquired')
    
    
Or to keep trying to get the mutex until a given timeout elapses:

    with timed_acquire_mutex('mutex_name'):
        # Do something without any racing condition with other processes
        ...

License: Dual-licensed under LGPL and Apache 2.0

Copyright: Brainwy Software
Author: Fabio Zadrozny
"""

import re
import sys
import tempfile
import time
import traceback
import weakref

from robocode_ls_core.constants import NULL, IS_PY2
from robocode_ls_core.robotframework_log import get_logger
import threading


log = get_logger(__name__)


def check_valid_mutex_name(mutex_name):
    # To be windows/linux compatible we can't use non-valid filesystem names
    # (as on linux it's a file-based lock).

    regexp = re.compile(r'[\*\?"<>|/\\:]')
    result = regexp.findall(mutex_name)
    if result is not None and len(result) > 0:
        raise AssertionError("Mutex name is invalid: %s" % (mutex_name,))


_mutex_name_to_info = weakref.WeakValueDictionary()
_lock = threading.Lock()


def get_tid():
    if IS_PY2:
        return threading._get_ident()  # @UndefinedVariable
    else:
        return threading.get_ident()  # @UndefinedVariable


def _mark_prev_acquired_in_thread(system_mutex):
    with _lock:
        _mutex_name_to_info[system_mutex.mutex_name] = system_mutex


def _verify_prev_acquired_in_thread(mutex_name):
    with _lock:
        system_mutex = _mutex_name_to_info.get(mutex_name)
        if (
            system_mutex is not None
            and system_mutex.get_mutex_aquired()
            and system_mutex.thread_id == get_tid()
        ):
            raise RuntimeError(
                "Error: this thread has already acquired a SystemMutex and it's not a reentrant mutex (so, this would never work)!"
            )


if sys.platform == "win32":

    import os

    class SystemMutex(object):
        def __init__(self, mutex_name, check_reentrant=True):
            """
            :param check_reentrant:
                Should only be False if this mutex is expected to be released in
                a different thread.
            """
            check_valid_mutex_name(mutex_name)
            self.mutex_name = mutex_name
            self.thread_id = get_tid()
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                os.unlink(filename)
            except Exception:
                pass
            try:
                handle = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                try:
                    try:
                        pid = str(os.getpid())
                    except Exception:
                        pid = "unable to get pid"
                    os.write(handle, pid)
                except Exception:
                    pass  # Ignore this as it's pretty much optional
            except Exception:
                self._release_mutex = NULL
                self._acquired = False
                if check_reentrant:
                    _verify_prev_acquired_in_thread(mutex_name)
            else:

                def release_mutex(*args, **kwargs):
                    # Note: can't use self here!
                    if not getattr(release_mutex, "called", False):
                        release_mutex.called = True
                        try:
                            os.close(handle)
                        except Exception:
                            traceback.print_exc()
                        try:
                            # Removing is optional as we'll try to remove on startup anyways (but
                            # let's do it to keep the filesystem cleaner).
                            os.unlink(filename)
                        except Exception:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True
                _mark_prev_acquired_in_thread(self)

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()


else:  # Linux
    import os
    import fcntl  # @UnresolvedImport

    class SystemMutex(object):
        def __init__(self, mutex_name, check_reentrant=True):
            """
            :param check_reentrant:
                Should only be False if this mutex is expected to be released in
                a different thread.
            """
            check_valid_mutex_name(mutex_name)
            self.mutex_name = mutex_name
            self.thread_id = get_tid()
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                handle = open(filename, "w")
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception:
                self._release_mutex = NULL
                self._acquired = False
                if check_reentrant:
                    _verify_prev_acquired_in_thread(mutex_name)
                try:
                    handle.close()
                except Exception:
                    pass
            else:

                def release_mutex(*args, **kwargs):
                    # Note: can't use self here!
                    if not getattr(release_mutex, "called", False):
                        release_mutex.called = True
                        try:
                            fcntl.flock(handle, fcntl.LOCK_UN)
                        except Exception:
                            traceback.print_exc()
                        try:
                            handle.close()
                        except Exception:
                            traceback.print_exc()
                        try:
                            # Removing is pretty much optional (but let's do it to keep the
                            # filesystem cleaner).
                            os.unlink(filename)
                        except Exception:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True
                _mark_prev_acquired_in_thread(self)

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()


class _MutexHandle(object):
    def __init__(self, system_mutex, mutex_name):
        self._system_mutex = system_mutex
        self._mutex_name = mutex_name
        log.info("Obtained mutex: %s", mutex_name)

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self._system_mutex.release_mutex()
        log.info("Released mutex: %s", self._mutex_name)


def timed_acquire_mutex(mutex_name, timeout=10, sleep_time=0.15, check_reentrant=True):
    """
    Acquires the mutex given its name, a number of attempts and a time to sleep between each attempt.

    :throws RuntimeError if it was not possible to get the mutex in the given time.

    To be used as:

    with timed_acquire_mutex('mutex_name'):
        # Do something without any racing condition with other processes
        ...
        
        
    :param check_reentrant:
        Should only be False if this mutex is expected to be released in
        a different thread.
    """
    finish_at = time.time() + timeout
    while True:
        mutex = SystemMutex(mutex_name, check_reentrant=check_reentrant)
        if not mutex.get_mutex_aquired():
            if time.time() > finish_at:
                log.info("Unable to obtain mutex: %s", mutex_name)
                raise RuntimeError(
                    "Could not get mutex: %s after: %s secs." % (mutex_name, timeout)
                )

            time.sleep(sleep_time)

            mutex = None
        else:
            return _MutexHandle(mutex, mutex_name)


def generate_mutex_name(target_name, prefix=""):
    """
    A mutex name must be a valid filesystem path, so, this generates a hash
    that can be used in case the original name would have conflicts.
    """
    import hashlib

    if not isinstance(target_name, bytes):
        target_name = target_name.encode("utf-8")

    return prefix + (hashlib.sha224(target_name).hexdigest()[:16])