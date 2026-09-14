"""El reloj del sistema: hora local, naive. Lo inyecta main.py; en los tests se
usa un reloj fijo."""

from datetime import datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now()
