# Video Analysis App — Architecture & Product Directive

*Generated via 3-round antagonistic self-critique planning session, 2026-04-14*

---

## What it does

Analyzes Instagram Reels (by URL paste or file upload) using multi-modal AI. Extracts frames, transcribes audio, reads on-screen text, then scores each video against a versioned content rubric. Produces both machine-readable scores and plain-English creator-facing narrative. Supports flagging videos as success benchmarks and comparing all analyses against benchmark patterns.

**What it is not:** A scheduling tool, a publishing tool, a competitor tracker, or a real-time analytics dashboard. It is a structured analysis and pattern library.

**Long-term objective:** Deeply understand why certain videos are successful, break them into patterns, and surface those patterns for emulation and testing.

**Comparable tools:** memories.ai, alison.ai

---

## Users

Internal tool for non-technical UGC creators at yourTMJ. UI must be usable by non-engineers. Single shared password for access (env var).

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python FastAPI | Consistent with existing repo; minimal |
| Frontend | Preact (CDN, no build) + Alpine.js | No build step, ~3kb, reactive panels/drill-down |
| Database | SQLite (WAL mode) | Zero infra; handles light concurrency |
| Video download | yt-dlp + manual upload fallback | Resilient to Instagram blocking |
| Frame extraction | ffmpeg | Free, fast |
| Transcription | OpenAI Whisper API | Best quality/price |
| Vision | Claude claude-sonnet-4-6 vision | Multi-modal, handles frames + on-screen text |
| Synthesis | Claude claude-sonnet-4-6 | Same model, structured output |
| Auth | HTTP Basic Auth, single env var | One FastAPI middleware line |

No build toolchain. Minimize lines of code.

---

## Analysis Pipeline

```
Input: URL paste or file upload (.mp4)
  ↓
[Download/ingest]
  yt-dlp (URL) or direct upload
  → structured error messages for private/geo-blocked/invalid/too-long
  ↓
[Frame extraction] — ffmpeg
  Always extract: t=0, 1, 2, 3s   ← hook coverage guaranteed
  + keyframes (scene cuts)
  + 1 frame every 5s
  Dedup + cap at 20 frames total
  ↓
[Phase 1 — parallel async]
  ├── Whisper API: full transcription
  └── Claude Vision (up to 20 concurrent calls): per-frame description + on-screen text
  ↓
[Phase 2 — synthesis]
  Input: frame descriptions + timestamps + transcript + rubric (versioned)
  Output: structured JSON
    rubric_scores:     { hook: 8, pacing: 6, ... }     ← machine-readable
    rubric_narrative:  { hook: "Your hook opens on...", ... }  ← creator-readable
    tags:              ["direct-to-cam", "fast-cut", "text-overlay"]
    summary:           one paragraph plain English
  ↓
SQLite storage (rubric_id FK → rubrics table)
  ↓
Frontend renders embed + analysis panel
```

---

## Content Rubric (v1)

Derived from Hormozi's hook framework, VidIQ retention research, and TikTok creator guides.

| Dimension | What's scored |
|---|---|
| Hook | Pattern interrupt in frames 0–3s? Opening line: question, bold claim, or visual shock? |
| Pacing | Cuts per minute. Faster in hook? Pace matches topic energy? |
| Speaker style | Direct-to-camera / voiceover / text-only / B-roll narration |
| Retention arc | Does content escalate? Is there a payoff? CTA at natural endpoint? |
| Visual variety | # distinct scenes, text overlays, transitions |
| Audio | Music present? Ducks under speech? Sound effects? |
| On-screen text | Key claims reinforced via text? Text timed to speech? |
| CTA | Present? Where (beginning/middle/end)? What type (follow, buy, comment)? |

Each dimension produces a score (1–10) **and** a plain-English narrative sentence for the creator.

---

## Rubric Versioning

The `rubrics` DB table stores:
```
id, version, created_at, system_prompt_text, dimension_names (JSON)
```

Every `Analysis` row has `rubric_id` FK. Viewing an old analysis shows the exact criteria used. Updating the rubric does not auto-re-score old analyses — a "Re-analyze" button runs Phase 2 only (frame descriptions cached, cheap: ~$0.015/video).

---

## UI Layout

- **List view:** All analyzed videos in a grid. Each card shows embed + high-level summary.
- **Detail panel:** Double-click any dimension → expanded narrative + score breakdown appears.
- **Benchmark tab:** Aggregate patterns across all videos flagged `is_benchmark = true`.
  - Most common tags, median rubric scores, most common hook types
  - Per-video: "vs. Benchmarks" sidebar showing score deltas

---

## Success Metrics

- **Phase 1:** Views (manually entered)
- **Phase 2:** Likes, purchases, 50% watch time (manually entered)
- **Future:** Instagram Graph API for automatic population

Manual entry UI: "Add Metrics" button → modal with optional fields per video.

---

## Error Handling

| Failure | User message |
|---|---|
| Private reel | "This reel is private or login-required. Download manually and upload the .mp4." |
| IP blocked | "Instagram blocked the download. Try again in a few minutes or upload the file directly." |
| Invalid URL | "Paste an Instagram Reel URL (instagram.com/reel/...)" |
| Reel too long | "Reels over 90s are not supported yet." |

---

## Cost Estimate

| Operation | Per video |
|---|---|
| Whisper (60s audio) | ~$0.006 |
| Claude Vision (20 frames) | ~$0.10 |
| Claude synthesis call | ~$0.015 |
| **Total** | **~$0.12–0.15** |

50 videos/week → ~$6–8/week
200 videos/week → ~$24–30/week
Re-analysis only (rubric update) → ~$0.015/video

---

## Integration with yourTMJ Brief Generator

Output JSON includes a `content_item` key mapping directly to the existing `ContentItem` schema in `schema.py`. The brief generator can ingest analyzed videos with zero schema changes.

---

## Phasing

**Phase 1:** URL input → pipeline → analysis view. Manual metric entry. Shared password auth.

**Phase 2:** Benchmark aggregation, rubric evolution tooling, Instagram Graph API for automatic metrics, yourTMJ brief generator integration.

---

## Open Decisions (deferred)

1. Should benchmark comparison show inline on every analysis, or only when explicitly toggled?
2. Should re-analysis on rubric update be automatic for all videos, or manual per video?
