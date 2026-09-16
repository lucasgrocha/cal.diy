# CLAUDE.md

## Business hours & timezones

- Standard business hours: Must follow the user availability.
- The app must support **multiple timezones** — users can be in different countries/timezones, so scheduling requires timezone conversion (store times in UTC, convert to each user's local timezone for display).
- Holidays: **no special handling**. Only day-of-week and time-of-day matter; holidays/non-business days are not excluded from availability.
