# Reiri ecosystem research

Findings from a web and GitHub survey on 10 September 2026. Recorded so the
context is not lost between contributors. Update as things change.

## Summary

- Daikin publishes no API for Reiri hubs. The local WebSocket on port 52001 is
  the only local control path; a full port sweep of a DCPH01 found only 80 and
  52001 open, and no Modbus.
- Two other Home Assistant custom integrations for Reiri hubs appeared in
  August and September 2026. One uses the same `reiri` domain as this project.
- The protocol this integration implements has now been independently
  reverse-engineered three times with matching results.

## Reiri hardware

| Model | Product | Notes |
|---|---|---|
| DCPH01 | Reiri for Home | Original Home hub. Model reported as `H01` in `sys_info`. |
| DCPH02 | Reiri for Home Lite | Cut-down Home hub. |
| DCPF01 | Reiri for Office | Office hub. Same wire protocol per the Office integration. |
| DCPA01 | DIII-Net to Modbus adapter | Not a Reiri hub. Alternative route to VRV control via Modbus RTU. |
| F10 | (model code) | Controllers reporting `F10` wrap payloads in an `msm` envelope (see protocol notes). |

Vendor FAQ says to unblock ports 80, 52000, 52001, 52010 and 123. The cloud relay
is `wss://reiri-sin.daikin.com.sg:52010`; the web app falls back to it when the
local socket fails. Google Home and Alexa support is cloud only.

## Other implementations

### jamiepenney/reiri (Home Assistant, DCPH01)

<https://github.com/jamiepenney/reiri>

- Created 9 September 2026, 12 commits in one day. No licence, no release, not
  in the HACS default list as of 10 September 2026.
- **Declares domain `reiri`, the same as this integration.** The two cannot be
  installed in the same Home Assistant instance. Coordination is on the backlog.
- `local_push`: takes an `mplist` baseline then applies `cos` deltas.
- Has a pytest suite and a live end-to-end test.
- Ships `PROTOCOL.md`, a 300-line reverse-engineering write-up tested on one
  ducted unit (model `H01`, firmware 1.6.0, Singapore). Key findings that this
  project has not yet acted on:
  - **`fanstep` writes are silently dropped by the hub.** Observed lags of
    75 s to never. Their client writes optimistically, reads back after ~45 s
    and re-sends up to three times. `stat`, `sp` and `mode` apply reliably in
    5 to 10 s.
  - **The hub holds a small pool of sessions.** Exhausting it makes the hub go
    silent for minutes while still accepting TCP connections. Keep one session,
    close it cleanly, back off to five minutes between reconnects.
  - **`temp` is the return-air sensor.** With the fan off it reads several
    degrees high (26 vs a wall panel at 21). Trustworthy only while `fan` is
    `on`.
  - **UDP 52001 carries a discovery broadcast.** Not yet characterised.
  - RSA padding is OAEP-SHA1. PKCS#1 v1.5 unpadding "succeeds" on the same
    ciphertext but yields garbage; require a 16-byte plaintext.
  - Setpoint limits arrive as `csp_range`, `hsp_range` and `sp_step`.
  - Fan value `M` is listed by the app but was never observed applying on
    their three-step unit.

### themodernhousebr/reiri-for-office (Home Assistant, DCPF01)

<https://github.com/themodernhousebr/reiri-for-office>

- Created 11 August 2026. MIT licence, release v0.1.9. Domain `reiri_for_office`,
  so no clash. README in Portuguese.
- Independently confirms: read `csp`/`hsp`, write `sp`; flap positions as
  integers plus `S` for swing; `cos` pushes; `op` reply `result: OK`.
- Adds a 1.2 s debounce on `flap` writes, and a "conservative" mode policy for
  slave units that follows the master's mode.
- Notes a PKCS#1 v1.5 fallback for the RSA step, which the DCPH01 write-up
  argues is wrong. Treat OAEP-SHA1 as canonical.

### Kristian-Tan/reiri-daikin-websocket-inspector (tool, 2022)

<https://github.com/Kristian-Tan/reiri-daikin-websocket-inspector>

Node script from November 2022 for decrypting browser-to-hub traffic. Earliest
public description of the RSA-then-AES handshake. Tested on controller
version 1.1.18, model H01, Singapore. No integration followed.

## Demand signals

- Home Assistant community, "Daikin Reiri Integration", 16 June 2024. One post
  asking whether integration is possible, no replies, 3 likes, over 400
  incoming links. It is the top web search result for the topic.
  <https://community.home-assistant.io/t/daikin-reiri-integration/740042>
- Homey community, "Daikin Reiri integration", 22 August 2026. Request for a
  local-communication integration; a developer offered a cloud-only app.
  <https://community.homey.app/t/daikin-reiri-integration/158624>

## Alternatives without a Reiri hub

All need extra hardware on the DIII-Net bus.

- Daikin DCPA01 DIII-Net to Modbus RTU adapter.
- HMS/Intesis Daikin VRV gateway, supported by Home Assistant's IntesisHome
  integration.
- CoolAutomation CoolMaster.
- P1P2MQTT, which lists Daikin DIII-Net F1/F2 as readable.

## Protocol notes confirmed on this project's hardware

Live read-only testing on 10 September 2026 against a Daikin VRV system with
nine indoor units, point IDs `dcpa1:1-00001` to `-00010`:

- Rejected logins are answered in **plaintext**:
  `[null, null, ["login", {"result": "wrong_passwd"}]]`. Codes seen:
  `wrong_passwd`, `no_acname` (unknown user), `block_period` (3 s lockout after
  any failed attempt, per the vendor web app).
- Unsolicited frames on an idle connection: `cos` several times a minute, and
  an occasional plaintext `time`.
- `sp` is `null` in `mplist`; `csp` and `hsp` carry the setpoints.
- `otemp` can be `0` on an idle unit.
- `flap` is absent on units without louvre control.
- Every unit reports `csp_range`, `hsp_range`, `sp_step`, `csp_limit`,
  `hsp_limit` and `temp_limit`.

## Sources

- Daikin Solutions Reiri FAQ: <https://www.daikin-solutions.com/faq>
- Daikin Australia, Reiri Controller for Home: <https://www.daikin.com.au/products/commercial/system-controllers/reiri-home>
- Reiri for Home Lite installation manual: <https://www.manualslib.com/manual/3275906/Daikin-Reiri-For-Home-Lite.html>
- Reiri Solution brochure: <https://www.daikinmea.com/content/dam/DameaWebsite/ProductGroups/Controls/Reiri/Reiri%20Solution.pdf>
- DIII-NET/Modbus adapter: <https://daikincomfort.com/docs/default-source/general/vrv/pf-diiinet.pdf>
- HMS Daikin VRV gateway: <https://www.hms-networks.com/p/inwmpdai001r000-daikin-vrv-and-sky-systems-to-home-automation-interface>
- IntesisHome integration: <https://www.home-assistant.io/integrations/intesishome/>
- P1P2MQTT: <https://github.com/Arnold-n/P1P2MQTT>
