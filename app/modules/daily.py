from app.modules.weekly import *  # noqa: F401,F403
from app.modules.weekly import smart_schedule, build_schedule  # noqa: F401

daily = smart_schedule
build_daily = build_schedule
