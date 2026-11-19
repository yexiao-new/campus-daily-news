"""每日定时任务：到达设定时间后自动抓取并生成当天 Word。"""
import datetime as dt
import threading


class Scheduler:
    def __init__(self, job, store, tick_seconds=20):
        self.job = job
        self.store = store
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="digest-scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.tick_seconds):
            try:
                self._tick()
            except Exception as exc:  # 定时任务不能把进程带崩
                self.store.meta_set("last_scheduler_error", f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {exc}")

    def _tick(self):
        from core import config as cfgmod

        cfg = cfgmod.load()
        digest_cfg = cfg.get("digest") or {}
        target = str(digest_cfg.get("time") or "08:00").strip()
        now = dt.datetime.now()
        today = now.date().isoformat()

        # 没到点，或今天已经跑过，直接跳过
        if now.strftime("%H:%M") < target:
            return
        if self.store.meta_get("last_auto_day") == today:
            return

        self.store.meta_set("last_auto_day", today)
        try:
            result = self.job()
            self.store.meta_set("last_auto_at", f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}")
            added = result.get("added", 0) if isinstance(result, dict) else 0
            self.store.meta_set("last_auto_summary", f"新增 {added} 条，文档：{result.get('digest', '—')}")
        except Exception as exc:
            self.store.meta_set("last_auto_error", f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {exc}")
