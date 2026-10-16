# Daily chart quick ranges

- Add compact 7 / 30 / 90 day shortcuts above the production daily chart, with selected styling and keyboard focus.
- Windows include the selected assessment day: seven days means current minus six days through current.
- Show a shortcut only when every calendar day is present in the API's availableDates for this unit, indicator group and reporting period. Do not borrow dates across periods or gaps. Historical assessment dates remain the anchor.
- Preserve both calendars and the selected chart indicator. A shortcut updates the baseline through the existing comparison GET; no automatic reads, polling, collection, Credit operation or backend change.
- Guard repeated clicks, stale context and unoffered ranges; retain existing abort and response validation.
- TypeScript and model/chart/calendar/panel/UI tests PASS, including 6/7, 29/30 and 89/90 day boundaries, gaps, leap year, historic anchor, active button and one GET per click.
- Source/build updated locally; not deployed in this step.
