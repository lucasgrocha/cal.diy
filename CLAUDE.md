# CLAUDE.md

## Business hours & timezones

- Reference timezone: **UTC**. All stored/business-logic timestamps use UTC as the neutral baseline.
- Standard business hours: **Monday–Friday, 09:00–18:00** (UTC reference).
- The app must support **multiple timezones** — users can be in different countries/timezones, so scheduling requires timezone conversion (store times in UTC, convert to each user's local timezone for display).
- Holidays: **no special handling**. Only day-of-week and time-of-day matter; holidays/non-business days are not excluded from availability.
