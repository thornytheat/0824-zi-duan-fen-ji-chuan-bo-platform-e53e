from app.modules.weekly import *  # noqa: F401,F403
from app.modules.weekly import (  # noqa: F401
    build_schedule, smart_schedule, schedule_from_payload,
    weekly_schedule, daily_schedule, weekly_labels, daily_labels,
)

schedule = smart_schedule
calendar = smart_schedule
create_schedule = build_schedule
