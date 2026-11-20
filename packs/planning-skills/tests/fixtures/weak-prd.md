# Fixture: weak requirements doc

# PRD: Skip Button v2

## Overview
We will add a Skip button to the weekly plan page. It sits under "Next delivery",
uses the secondary button style, and opens a modal with a date picker. On confirm we
call `PATCH /subscriptions/{id}/deliveries` with `status=skipped`, then refresh.

## Requirements
1. Skip button on the plan page.
2. Modal with date picker.
3. Confirmation toast.
4. Email confirmation.
5. Admin tool shows skipped weeks.

## Success
Users will love being able to skip, and it will improve retention.

## Timeline
Two sprints.

(Expected: foregone conclusion, unfalsifiable and launch-day surprise failure modes;
approver, operator and analyst Missing; builder and tester at best Needs work.)
