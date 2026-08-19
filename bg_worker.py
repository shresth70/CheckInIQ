"""
Background worker for ID-card generation + emailing.

WHY THIS FILE EXISTS
---------------------
Before this fix, every check-in did:

    threading.Thread(target=send_id_card_email, args=(...)).start()

That spawns a brand-new, uncapped thread per check-in, and each one of
those threads launched its OWN Chromium browser via Playwright just to
screenshot a single card. Chromium launches are slow (1-3s) and use a
few hundred MB of RAM each. If several people check in within a few
seconds of each other (exactly what happens at a real registration
desk), you'd get several Chromium processes starting at the same time,
competing for CPU/RAM -> everything lags or looks like it "resets".

THE FIX
-------
- One Chromium browser is launched ONCE and kept running for the life
  of the app (see email_service.get_persistent_browser()).
- Jobs (one per check-in) go into a queue instead of spawning a raw
  thread. A single dedicated worker thread pulls jobs off the queue
  and handles them one at a time, reusing the same browser + the
  shared SMTP connection.

Because the expensive "launch a browser" step only happens once ever
(not once per guest), each job now takes a fraction of a second
instead of seconds - so processing them one-by-one is still plenty
fast, and it removes the resource contention that was causing the lag.

Playwright's sync API must only be used from the thread that started
it - that's why the browser is created *inside* this worker thread
and nothing else should call get_persistent_browser().
"""

import queue
import threading
import traceback

from email_service import send_id_card_email, get_persistent_browser

_job_queue = queue.Queue()


def _worker_loop():
    while True:
        args = _job_queue.get()
        try:
            browser = get_persistent_browser()
            send_id_card_email(*args, browser=browser)
        except Exception:
            print("[BG WORKER ERROR]")
            traceback.print_exc()
        finally:
            _job_queue.task_done()


_worker_thread = threading.Thread(target=_worker_loop, daemon=True)
_worker_thread.start()


def enqueue_id_card_email(guest_name, guest_email, event_name, event_date,
                           event_venue, guest_id, qr_bytes):
    """Schedule an ID-card email to be rendered + sent in the background.
    Returns immediately - use this instead of threading.Thread(...)."""
    _job_queue.put((guest_name, guest_email, event_name, event_date,
                     event_venue, guest_id, qr_bytes))
