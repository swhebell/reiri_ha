# Backlog

Open items from the September 2026 code review and the ecosystem research in
[RESEARCH.md](RESEARCH.md). Numbers in brackets are the original review item
numbers, kept so discussion threads stay traceable. Items are grouped by
priority, not by area. Status as of 10 September 2026.

## Done

| Item | Shipped in |
|---|---|
| [1] Reject duplicate controllers; unique ID on config entries | 1.2.3 |
| [3] Missing temperatures report as unknown, not 0.0 | 1.2.3 |
| [9] `ConfigEntryAuthFailed` plus reauth flow; `block_period` treated as transient | 1.2.3 |
| [13] Match hub replies on parsed command name, not substring | 1.2.3 |
| [22] hassfest and HACS validation workflows; issue template | 1.2.4 |
| [23] Brand icon (served locally by HA 2026.3+) | 1.2.4 |
| `via_device` to `via_device_id` migration | 1.2.2 |

## High priority

- **Domain clash with jamiepenney/reiri.** Both integrations declare domain
  `reiri`. Open an issue on their repo proposing coordination: a rename on
  their side, or merging effort. This project is older, released and queued
  for the HACS default list (PR hacs/default#10821), so it has the stronger
  claim to the domain.
- **Fan speed writes need verify-and-retry.** The DCPH01 write-up shows the hub
  silently drops `fanstep` writes. Confirm on this hardware, then: write
  optimistically, read back after ~45 s, re-send up to three times, resync if
  it never lands. Extends the existing optimistic-update latch.
- **[16] Entity availability.** Override `available` so an entity goes
  unavailable when its point disappears from `coordinator.data` or the
  coordinator fails, instead of freezing on stale values. `ReiriClimate`
  currently overrides `_handle_coordinator_update` and always writes state.
- **[12] Timeouts leave the socket in an unknown state.** `get_point_list` and
  `operate` retry only on `ConnectionClosed`/`BrokenPipeError`. A
  `ReiriConnectionError` from a read timeout is not retried and the socket is
  kept. Close the socket on timeout so the next poll reconnects cleanly, but
  see the session-pool note below before making reconnects more aggressive.
- **Respect the hub's session pool.** The hub goes silent for minutes if too
  many sessions are opened. Keep exactly one session, close cleanly on unload,
  and cap reconnect backoff at five minutes. Audit config-flow validation,
  which opens and closes a second session while the integration is running.

## Medium priority

- **Use `cos` pushes instead of, or alongside, polling.** The hub pushes
  change-of-state deltas several times a minute. Take an `mplist` baseline
  after login, apply `cos` deltas as they arrive, and poll `mplist` only as a
  periodic resync. Would make the integration `local_push` and remove most of
  the >60 s latency problem. Requires a reader task on the socket and a
  reply-matching queue, since pushes interleave with command replies.
- **[7] Setpoint limits and step.** Expose `min_temp`, `max_temp` and
  `target_temperature_step` from `csp_range`/`hsp_range` and `sp_step`, which
  every unit reports. Pick the range by active mode.
- **[8] Entity naming.** Adopt `_attr_has_entity_name = True`; climate entity
  name `None`, sensors named "Filter", "Compressor", "Outdoor temperature".
  Changes friendly names for existing users, so ship in a minor release with a
  changelog warning.
- **[2] Standard fan mode constants.** Use `FAN_AUTO`, `FAN_LOW`, `FAN_MEDIUM`,
  `FAN_HIGH` for the modes that map, keep `medium-low`/`medium-high` custom.
  Gets translations and icons in the UI. Also [20]: replace the two if-chains
  with one dict pair as already done for HVAC modes.
- **[5] Swing capability default.** `flap_cap.D` defaults to 3 when missing,
  so units without louvre data get a swing selector that does nothing. Hide
  swing unless the capability is explicitly reported.
- **[10] Reconfigure flow.** Let the user change the hub IP without deleting
  the entry.
- **[11] Coordinator backoff duplicates HA's own.** `DataUpdateCoordinator`
  already backs off and de-duplicates failure logging. Verify against HA 2026.9
  and delete the hand-rolled version if redundant.
- **[21] Diagnostics.** Add `diagnostics.py` dumping the redacted point list so
  bug reports carry the data shapes that have caused most issues.
- **`temp` is the return-air sensor.** Reads high while the fan is off.
  Document in the README; consider an attribute flagging the reading as stale
  when `fan` is `off`.

## Low priority

- **[4] Setpoint behaviour in auto/dry/fan modes.** `sp` is `null` in
  `mplist` on this hardware, so target temperature is unknown outside cool and
  heat. Decide whether to show a low/high range in auto or hide the setpoint.
- **[6] Magic 60 s latch.** Move to a constant in `const.py`; switch
  `time.time()` to `time.monotonic()`.
- **[14] Comment the SHA1 OAEP padding** as dictated by the hub so nobody
  "fixes" it.
- **[15] `PARALLEL_UPDATES = 0`** in each platform, since the client already
  serialises behind a lock.
- **[17] Tests.** None exist. `pytest-homeassistant-custom-component` plus a
  fake `ReiriClient` would cover mode mapping, the optimistic latch, the config
  flow and reauth. A recorded handshake would cover the client.
- **[18] Typing and `entry.runtime_data`.** Type the constructors, replace the
  `hass.data` dict with a typed `ReiriConfigEntry`. Drop the no-op
  `CONNECTION_CLASS` (already removed in 1.2.3).
- **[19] Lazy logging.** Replace f-string log calls in `reiri_client.py` with
  `%s` formatting.
- **UDP discovery on 52001.** The hub broadcasts on UDP 52001. Characterise the
  packet and, if usable, add discovery to the config flow.
- **`F10` controllers.** Payloads are wrapped in an `msm` envelope with an
  active-site field. Not handled; no known user yet.
- **Screenshots in the README.** Climate card and device page.

## Publicity (not code)

- Reply in the June 2024 Home Assistant community thread linking the repo.
- Post in Share your Projects and r/homeassistant (drafts exist in the session
  history of 10 September 2026; include model numbers DCPH01, DCPH02, DCPA01).
- Watch hacs/default#10821 for the bot's checks and any reviewer comments.
