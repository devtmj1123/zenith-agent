from __future__ import annotations
import platform
import time
from dataclasses import dataclass


@dataclass
class EnvironmentState:
    os_name: str
    hostname: str
    time_of_day: str
    day_of_week: str
    is_work_hours: bool


class EnvironmentSensor:
    def sense(self) -> EnvironmentState:
        now = time.localtime()
        hour = now.tm_hour
        day = time.strftime("%A", now)

        return EnvironmentState(
            os_name=platform.system(),
            hostname=platform.node(),
            time_of_day=time.strftime("%H:%M", now),
            day_of_week=day,
            is_work_hours=9 <= hour <= 18 and day not in ("Saturday", "Sunday"),
        )

    def get_context_string(self) -> str:
        env = self.sense()
        return (
            f"OS: {env.os_name}, Host: {env.hostname}, "
            f"Time: {env.time_of_day} {env.day_of_week}, "
            f"Work hours: {env.is_work_hours}"
        )
