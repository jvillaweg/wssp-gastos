from datetime import datetime, timedelta
import collections

class RateLimiter:
    def __init__(self):
        self.user_windows = collections.defaultdict(list)
        self.msg_limit = 30
        self.window_seconds = 300

    def check(self, user_id):
        now = datetime.utcnow()
        window = self.user_windows[user_id]
        # Remove old timestamps
        self.user_windows[user_id] = [t for t in window if (now - t).total_seconds() < self.window_seconds]
        if len(self.user_windows[user_id]) >= self.msg_limit:
            return False
        self.user_windows[user_id].append(now)
        return True

    def abuse(self, user_id):
        # If user consistently exceeds, trigger block
        ...
