from __future__ import annotations
import time
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

class PipelineLogger:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.console = Console()
        self.progress = None
        self.task = None
        self.phase = ''
        self.total_tokens = 0
        self.started_at = None

    def start(self):
        if not self.enabled or self.progress is not None:
            return
        self.started_at = time.time()
        self.progress = Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), BarColumn(), TaskProgressColumn(), TextColumn('[cyan]{task.completed}/{task.total} Chunks'), TimeRemainingColumn(), console=self.console, transient=False)
        self.progress.start()

    def stop(self):
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
            self.task = None

    def _print(self, msg):
        if not self.enabled:
            return
        (self.progress.console if self.progress is not None else self.console).print(msg)

    def set_phase(self, name, total=1):
        self.phase = name
        if not self.enabled:
            return
        self.start()
        desc = f'[bold]{name}[/bold]'
        if self.task is None:
            self.task = self.progress.add_task(desc, total=max(1, int(total)))
        else:
            self.progress.update(self.task, description=desc, total=max(1, int(total)), completed=0)
        self.info(f'Phase started: {name}')

    def advance(self, n=1):
        if self.progress is not None and self.task is not None:
            self.progress.advance(self.task, n)

    def info(self, msg):
        self._print(f'[cyan][INFO][/cyan] {msg}')

    def api(self, model, latency, prompt_text='', response_text=''):
        tokens = (len(prompt_text or '') + len(response_text or '')) // 4
        self.total_tokens += tokens
        self._print(f'[green][API][/green] {model} | latency {latency:.2f}s | approx tokens {tokens} | total {self.total_tokens}')

    def retry(self, attempt, max_retries, delay, status):
        self._print(f'[yellow][RETRY][/yellow] attempt {attempt}/{max_retries} | status {status} | backoff countdown {delay:.1f}s')

    def worker(self, msg):
        self._print(f'[magenta][WORKER][/magenta] {msg}')

    def phase_done(self, name):
        self.info(f'Phase finished: {name}')

log = PipelineLogger()
logger = log
