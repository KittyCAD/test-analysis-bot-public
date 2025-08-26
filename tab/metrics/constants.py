from datetime import timedelta

DELTA_THRESHOLD = 0.25  # percentage point change to alert on metrics

ALERT_CACHE_KEY = "metrics:alert"
ALERT_CACHE_TIMEOUT = timedelta(days=1.5).total_seconds()
