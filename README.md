# Travel Disruption Agent Demo

The demo uses a simulated itinerary and flight data. Times below are local simulated times on October 20-21, 2026. The flight takes four hours, and dependent events require a 45-minute arrival buffer.

Run the successful replanning examples with:

```powershell
python -m travel_agent --delay-hours 4
python -m travel_agent --delay-hours 6
```

## Scenario 1: Four-Hour Flight Delay

**Original itinerary**
- Flight to Northstar City: October 20, 08:00-12:00
- Hotel check-in: October 20, 14:00-14:30
- Project kickoff meeting: October 20, 15:00-16:00
- Museum visit: October 21, 10:00-12:00

**Disruption:** Flight departure moves from 08:00 to 12:00; arrival moves from 12:00 to 16:00.

**Affected events:** Hotel check-in and project kickoff meeting depend on the flight and begin before the 16:45 arrival-plus-buffer time. The museum visit is unrelated and remains feasible.

**Agent decision:** Move the hotel after the required arrival buffer. Schedule the meeting after the hotel to avoid a time conflict. Preserve the unrelated activity.

**Final outcome**
- Flight: 12:00-16:00
- Hotel check-in: 16:45-17:15
- Project kickoff meeting: 17:15-18:15
- Museum visit: October 21, 10:00-12:00, unchanged
- Automatic replanning succeeds; no human intervention is needed.

## Scenario 2: Six-Hour Flight Delay

**Original itinerary**
- Flight to Northstar City: October 20, 08:00-12:00
- Hotel check-in: October 20, 14:00-14:30
- Project kickoff meeting: October 20, 15:00-16:00
- Museum visit: October 21, 10:00-12:00

**Disruption:** Flight departure moves from 08:00 to 14:00; arrival moves from 12:00 to 18:00.

**Affected events:** Hotel check-in and project kickoff meeting depend on the flight and begin before the 18:45 arrival-plus-buffer time. The museum visit is unrelated and remains feasible.

**Agent decision:** Move the hotel after the required arrival buffer, then schedule the meeting after the hotel to avoid a conflict. Preserve the unrelated activity.

**Final outcome**
- Flight: 14:00-18:00
- Hotel check-in: 18:45-19:15
- Project kickoff meeting: 19:15-20:15
- Museum visit: October 21, 10:00-12:00, unchanged
- Automatic replanning succeeds; no human intervention is needed.

## Scenario 3: Six-Hour Delay With an 18:30 Meeting Deadline

This scenario uses the same original itinerary as Scenario 2, but the meeting's latest allowed start is 18:30 on October 20.

**Original itinerary**
- Flight to Northstar City: October 20, 08:00-12:00
- Hotel check-in: October 20, 14:00-14:30
- Project kickoff meeting: October 20, 15:00-16:00; latest allowed start 18:30
- Museum visit: October 21, 10:00-12:00

**Disruption:** Flight departure moves from 08:00 to 14:00; arrival moves from 12:00 to 18:00. The meeting must start no earlier than 18:45 to satisfy the transfer buffer, which is later than its 18:30 deadline.

**Affected events:** Hotel check-in and project kickoff meeting depend on the flight. The museum visit is unrelated.

**Agent decision:** The hotel can be tentatively placed after arrival, but no conflict-free meeting slot is available within its allowed window. Stop the automatic replan and request human intervention; do not apply a partial itinerary update.

**Final outcome**
- Flight: 14:00-18:00, updated for the disruption
- Hotel check-in: 14:00-14:30, original time retained
- Project kickoff meeting: 15:00-16:00, original time retained
- Museum visit: October 21, 10:00-12:00, unchanged
- Human intervention is required because the meeting deadline cannot be met safely.

The human-intervention scenario is covered by `test_meeting_outside_allowed_window_requests_human_intervention` in `tests/test_travel_agent.py`.