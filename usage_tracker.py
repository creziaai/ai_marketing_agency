import datetime

# -------------------
# In-memory usage tracking (for testing)
# In production, use Firestore or MongoDB
# -------------------
USAGE_DB = {}

LIMIT = 5          # Max uses per period
COOLDOWN_HOURS = 3 # Cooldown after hitting limit (your original requirement)
PERIOD_HOURS = 3   # Time window after which usage resets automatically


def _cleanup_old_usage(uid):
    """Remove usage older than PERIOD_HOURS."""
    now = datetime.datetime.utcnow()
    if uid not in USAGE_DB:
        USAGE_DB[uid] = []
    USAGE_DB[uid] = [t for t in USAGE_DB[uid] if (now - t).total_seconds() < PERIOD_HOURS * 3600]


def can_use_tool(uid):
    """Check if user can use tool right now."""
    now = datetime.datetime.utcnow()
    _cleanup_old_usage(uid)
    usage_times = USAGE_DB.get(uid, [])

    if len(usage_times) >= LIMIT:
        last_use = usage_times[-1]
        elapsed_hours = (now - last_use).total_seconds() / 3600

        # If still within cooldown
        if elapsed_hours < COOLDOWN_HOURS:
            return False

        # Reset usage after cooldown
        USAGE_DB[uid] = []
        return True

    return True


def record_usage(uid):
    """Record a new usage event."""
    now = datetime.datetime.utcnow()
    _cleanup_old_usage(uid)
    if uid not in USAGE_DB:
        USAGE_DB[uid] = []
    USAGE_DB[uid].append(now)


def get_usage(uid):
    """Return usage info for frontend dropdown."""
    now = datetime.datetime.utcnow()
    _cleanup_old_usage(uid)
    usage_times = USAGE_DB.get(uid, [])

    if len(usage_times) >= LIMIT:
        last_use = usage_times[-1]
        elapsed_hours = (now - last_use).total_seconds() / 3600
        reset_in_hours = max(0, COOLDOWN_HOURS - elapsed_hours)
    else:
        reset_in_hours = 0

    reset_in_seconds = int(reset_in_hours * 3600)
    return {
        "count": len(usage_times),
        "max": LIMIT,
        "reset_in": reset_in_seconds
    }
