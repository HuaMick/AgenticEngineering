"""Question folder file watcher service.

Watches questions/pending/ and questions/answered/ folders for changes and
triggers notification callbacks. Uses watchdog library for filesystem monitoring
with debouncing to prevent notification spam.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class QuestionWatcherHandler(FileSystemEventHandler):
    """File system event handler for question folder changes.

    Watches questions/pending/ and questions/answered/ directories for file changes
    and triggers a notification callback when questions are added, modified, or removed.
    Includes debouncing to limit callback frequency to at most once per 2 seconds.
    """

    def __init__(self, plan_folder: Path, callback: Callable[[], None]):
        """Initialize the question watcher handler.

        Args:
            plan_folder: Path to the plan folder containing questions/ directory.
            callback: Function to call when questions change (no arguments).
        """
        super().__init__()
        self.plan_folder = plan_folder
        self.callback = callback

        # Debouncing: Track last notification time and use a lock for thread safety
        self._last_notification_time = 0.0
        self._debounce_seconds = 2.0
        self._lock = threading.Lock()
        self._pending_notification = False
        self._timer: Optional[threading.Timer] = None

        logger.debug(
            f"QuestionWatcherHandler initialized for {plan_folder} "
            f"(debounce={self._debounce_seconds}s)"
        )

    def _should_handle_event(self, event: FileSystemEvent) -> bool:
        """Check if this event should trigger a callback.

        Args:
            event: The filesystem event.

        Returns:
            True if event is for a .yml file in pending/ or answered/ directories.
        """
        # Ignore directory events
        if event.is_directory:
            return False

        # Only handle .yml files
        if not event.src_path.endswith('.yml'):
            return False

        # Ignore temporary files (e.g., .tmp, .swp)
        if '.tmp' in event.src_path or '.swp' in event.src_path:
            return False

        # Check if file is in pending/ or answered/ directory
        path = Path(event.src_path)
        parent_name = path.parent.name

        return parent_name in ('pending', 'answered')

    def _trigger_notification(self):
        """Trigger the notification callback with debouncing.

        Uses threading.Timer to delay notification and cancel/reschedule if
        more events arrive within the debounce window. This ensures at most
        one notification per 2 seconds even if many file changes occur.
        """
        with self._lock:
            current_time = time.time()
            time_since_last = current_time - self._last_notification_time

            # Cancel any pending timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            # If enough time has passed, notify immediately
            if time_since_last >= self._debounce_seconds:
                self._last_notification_time = current_time
                self._notify_safely()
            else:
                # Schedule notification for later
                delay = self._debounce_seconds - time_since_last
                self._timer = threading.Timer(delay, self._delayed_notify)
                self._timer.daemon = True
                self._timer.start()
                logger.debug(f"Notification scheduled in {delay:.2f}s")

    def _delayed_notify(self):
        """Execute delayed notification (called by Timer thread)."""
        with self._lock:
            self._last_notification_time = time.time()
            self._timer = None
            self._notify_safely()

    def _notify_safely(self):
        """Call the callback function with error handling."""
        try:
            logger.debug("Triggering question change callback")
            self.callback()
        except Exception as e:
            logger.error(f"Error in question watcher callback: {e}", exc_info=True)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events.

        Args:
            event: The file creation event.
        """
        if self._should_handle_event(event):
            logger.debug(f"Question file created: {Path(event.src_path).name}")
            self._trigger_notification()

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events.

        Args:
            event: The file modification event.
        """
        if self._should_handle_event(event):
            logger.debug(f"Question file modified: {Path(event.src_path).name}")
            self._trigger_notification()

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events.

        Args:
            event: The file deletion event.
        """
        if self._should_handle_event(event):
            logger.debug(f"Question file deleted: {Path(event.src_path).name}")
            self._trigger_notification()

    def on_moved(self, event: FileSystemEvent):
        """Handle file move events.

        Args:
            event: The file move event.
        """
        # For move events, check both source and destination
        if hasattr(event, 'dest_path'):
            src_path = Path(event.src_path)
            dest_path = Path(event.dest_path)

            # Check if move is between pending/answered (question lifecycle)
            if (src_path.parent.name in ('pending', 'answered') or
                dest_path.parent.name in ('pending', 'answered')):
                if src_path.suffix == '.yml' or dest_path.suffix == '.yml':
                    logger.debug(
                        f"Question file moved: {src_path.name} -> {dest_path.name}"
                    )
                    self._trigger_notification()


def start_question_watcher(
    plan_folder: Path,
    callback: Callable[[], None],
    daemon: bool = True
) -> Observer:
    """Start watching a plan's question folders for changes.

    Creates and starts an Observer thread that monitors the questions/pending/
    and questions/answered/ directories for file changes.

    Args:
        plan_folder: Path to plan folder (e.g., docs/plans/live/260203QT_question_tmux).
        callback: Function to call when questions change. Should reload questions
                 and update notifications.
        daemon: If True, run observer as daemon thread (default: True).

    Returns:
        Observer instance. Caller should keep reference and call stop_question_watcher()
        when done.

    Raises:
        ValueError: If plan_folder doesn't exist or doesn't contain questions/ directory.

    Example:
        >>> from pathlib import Path
        >>> def on_questions_changed():
        ...     print("Questions changed!")
        >>> observer = start_question_watcher(
        ...     Path("docs/plans/live/260203QT_question_tmux"),
        ...     on_questions_changed
        ... )
        >>> # ... do work ...
        >>> stop_question_watcher(observer)
    """
    # Validate plan_folder exists
    if not plan_folder.exists():
        raise ValueError(f"Plan folder does not exist: {plan_folder}")

    if not plan_folder.is_dir():
        raise ValueError(f"Plan folder is not a directory: {plan_folder}")

    # Create questions directory if it doesn't exist
    questions_dir = plan_folder / "questions"
    questions_dir.mkdir(parents=True, exist_ok=True)

    # Create pending and answered directories if they don't exist
    pending_dir = questions_dir / "pending"
    answered_dir = questions_dir / "answered"
    pending_dir.mkdir(exist_ok=True)
    answered_dir.mkdir(exist_ok=True)

    # Create event handler
    handler = QuestionWatcherHandler(plan_folder, callback)

    # Create observer
    observer = Observer()
    observer.daemon = daemon

    # Schedule watching for both pending and answered directories
    observer.schedule(handler, str(pending_dir), recursive=False)
    observer.schedule(handler, str(answered_dir), recursive=False)

    # Start observer thread
    observer.start()

    logger.info(
        f"Question watcher started for {plan_folder} "
        f"(pending={pending_dir}, answered={answered_dir})"
    )

    return observer


def stop_question_watcher(observer: Observer) -> None:
    """Stop a running question watcher.

    Cleanly stops the observer thread and waits for it to finish.

    Args:
        observer: Observer instance returned from start_question_watcher().

    Example:
        >>> observer = start_question_watcher(plan_folder, callback)
        >>> # ... do work ...
        >>> stop_question_watcher(observer)
    """
    if observer is None:
        logger.warning("Attempted to stop None observer")
        return

    try:
        observer.stop()
        observer.join(timeout=5.0)
        logger.info("Question watcher stopped")
    except Exception as e:
        logger.error(f"Error stopping question watcher: {e}", exc_info=True)
