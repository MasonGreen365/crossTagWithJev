# ISS Reference Sources

Distilled, verified reference list for the ISS (NORAD 25544) — real tracking/radar sources, and real recorded SatNOGS observations. Every URL below was actually fetched and confirmed working during research, not recalled from memory. Where something couldn't be confirmed, that's stated explicitly rather than guessed.

## Real-time tracking / pass prediction

- **N2YO** — https://www.n2yo.com/satellite/?s=25544
  Live interactive map (orbit/footprint), real-time lat/lon/altitude/speed/azimuth/elevation, pass predictions, has an API.
- **Heavens-Above** — https://www.heavens-above.com/orbit.aspx?satid=25544
  Orbital plane view, ground track map, current orbital parameters (eccentricity, inclination, altitude ~416–425 km, ~15.49 rev/day), pass predictions for a chosen observer location.
- **NASA "Spot the Station"** — https://www.nasa.gov/spot-the-station/
  (`spotthestation.nasa.gov` redirects here.) No embedded live map — it's an info page pointing to the mobile app for flyover alerts, plus links to raw trajectory data (.txt/.xml). The old interactive map page (`tracking_map.cfm`) is gone (404).

## Real radar imaging

- **Fraunhofer FHR (TIRA radar)** — https://www.fhr.fraunhofer.de/en/space/space-situational-awareness-technologies.html
  Confirms TIRA (Tracking and Imaging Radar) exists and is used for satellite/space-object imaging and calibration. **No public gallery of actual ISS radar images was found** on their English pages — this would require a specific published paper or press release not located in this pass. Treat "real radar imagery of the ISS" as **unconfirmed/not publicly reachable** rather than assuming it exists online somewhere.

## Orbital/TLE catalog sources

- **CelesTrak SATCAT entry** — https://celestrak.org/satcat/table-satcat.php?CATNR=25544
  Direct entry: "ISS (ZARYA)", international designator 1998-067A, launched 1998-11-20, status Active, with links to current GP/orbital element data. (This is the same source goTag's simulation already fetches live TLEs from.)
- **Space-Track** — query pattern `https://www.space-track.org/basicspacedata/query/class/satcat/NORAD_CAT_ID/25544/format/html`
  Requires an authenticated session — could not be independently verified without credentials (request timed out rather than resolving, consistent with login-gating). URL pattern given for reference only.

## SatNOGS — real recorded observations

- **Web UI, filtered to ISS** — https://network.satnogs.org/observations/?norad=25544
  Browsable list (thousands of observations — narrow further by status/date as needed).
- **SatNOGS DB satellite page** — https://db.satnogs.org/satellite/25544/
  Human-browsable transmitter catalog (50 transmitters: APRS, FM voice repeater, SSTV, Soyuz VHF, EVA suits, ICARUS, etc.) plus TLE submission history.

### Verified real observations with actual downloadable audio + waterfall data

(FM voice repeater mode, 437.800 MHz — not SSTV; an earlier-found SSTV observation, ID 15106541, was double-checked and confirmed to still have null audio/waterfall artifacts, so it's excluded here.)

1. **Observation 15102907** — https://network.satnogs.org/observations/15102907
   Station: EA5WA Pobla Llarga, Spain (39.104, -0.458). Mode V/U FM voice repeater, CTCSS 67.0 Hz, 437.800 MHz.
   - Audio: https://network-satnogs.freetls.fastly.net/media/data_obs/2026/10/2/17/15102907/satnogs_15102907_2026-10-02T17-51-15.ogg
   - Waterfall: https://s3.eu-central-1.wasabisys.com/satnogs-network/data_obs/2026/10/2/17/15102907/waterfall_15102907_2026-10-02T17-51-15.png

2. **Observation 15106025** — https://network.satnogs.org/observations/15106025
   Station: DF0OHM Turnstile VHF, Germany (49.453, 11.094). FM, 437.800 MHz. Audio + waterfall both verified present (same URL pattern as above).

3. **Observation 15098701** — https://network.satnogs.org/observations/15098701
   Station: PE0SAT-12, Netherlands (51.721, 5.030). FM voice repeater, 437.800 MHz, 180s pass, max elevation 55°. Audio, waterfall, and metadata all confirmed present on the observation page.

## How this fits goTag

These three FM-voice-repeater observations are the better candidates for grounding the "real radio signature" half of the simulation than the earlier SSTV one — they have actual downloadable audio and waterfall data, not just a decoded image, and FM voice is a more continuous signal type than SSTV's scheduled-event-only transmissions (see `docs/V1.md` for why continuity matters for picking a signal to simulate against). CelesTrak remains the TLE source already in use; N2YO/Heavens-Above are useful for a quick sanity-check of the live orbit by eye, not for anything the simulation code needs to call.
