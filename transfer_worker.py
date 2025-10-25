# transfer_worker.py
from PyQt5.QtCore import QThread, pyqtSignal
from job_manager import JobManager


class TransferWorker(QThread):
    finished_signal = pyqtSignal(int, int, int, str)  # (inserted, updated, deleted, status)
    progress_signal = pyqtSignal(int)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        self.progress_signal.emit(0)
        try:
            transfer = JobManager(self.config)
            transfer.run()
            self.progress_signal.emit(100)
            self.finished_signal.emit(
                len(transfer.to_insert),
                len(transfer.to_update),
                len(transfer.to_delete),
                "completed"
            )
        except Exception as e:
            self.progress_signal.emit(0)
            self.finished_signal.emit(0, 0, 0, f"failed: {e}")