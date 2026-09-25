# Ep 3 Watergate — v1.1 VO-TIMING v3 (pause/breath markup only)
**Author:** Script
**Date:** 2026-09-24
**Status:** VO-TIMING v3 for Cut (wording frozen = joint PASSed v1.1)
**Joint review:** `/workspace/fiction-to-fact/reviews/ep03-watergate-joint-v1.1-verifier.md` (JOINT PASS — YT early-hint v1.1 + podcast-extended v1)
**Supersedes (YT timing only):** `/workspace/fiction-to-fact/scripts/ep03-watergate-v1-vo-timing.md` · `/workspace/fiction-to-fact/scripts/ep03-watergate-v1-vo-timing-v2.md` (v1/v2 were for PASSed v1 wording — keep as archive; do not bake for v1.1)
**Wording source (frozen):** `/workspace/fiction-to-fact/scripts/ep03-watergate-v1.1-narration-only.md`
**Full draft (reference only):** `/workspace/fiction-to-fact/scripts/ep03-watergate-draft-v1.1.md`
**Christopher bake path suggestion:** `/workspace/fiction-to-fact/assembly/ep03/vo/ep03-full-christopher-v1.1-timing-v3.mp3` (+ `.vtt` + `-text.txt`)
**Voice lock:** `en-US-ChristopherNeural` · pitch **−8Hz** · rate **unlocked for naturalness** (Cut may try **−5%**; do **not** lock −10% on this bake unless Daniel reverts)
**Hard rule:** Pause/breath markup ONLY — spoken words, claims, fences, and meaning unchanged. Verifier: no re-gate (wording frozen = joint PASS).
**Density:** Same as Ep3 v2 / Daniel preferred — strip most mid-clause `[br]`; sentence-end `[p]` ~700–900ms; section `[P]` ~1.2–1.5s; `|` on sentence boundaries only (Aftermath true-now list).
**Do not publish. Do not Distro. Do not message agents.**

---

## Markup legend (Cut → edge-tts / SSML)

| Marker | Meaning | Suggested duration | edge-tts / SSML hint |
|--------|---------|--------------------|----------------------|
| `[br]` | Short breath (rare — appositive / em-dash only) | ~200–300 ms | `<break time="250ms"/>` (or insert silence in stitch) |
| `[p]` | Pause (default **between sentences**) | **~700–900 ms** | `<break time="800ms"/>` |
| `[P]` | Longer beat (section turns / cold-open punches) | **~1.2–1.5 s** | `<break time="1350ms"/>` |
| `\|` | Sentence-break chunk boundary only | n/a | Split TTS chunk here; no extra silence beyond adjacent `[p]`/`[P]` |

**v3 density rule:** Prefer sentence-end `[p]` / section `[P]`. Almost never put `[br]` mid-clause. Keep `|` only where a sentence ends and Cut should chunk (Aftermath “What is true now?” list).

Strip rule for wording check: remove `[br]` / `[p]` / `[P]` / `|` and whitespace adjacent to those markers only — remaining spoken text must match narration-only character-for-character (including `*italics*` / `**bold**` fence emphasis as in source).

---

## Full narration (VO-TIMING v3)

## COLD OPEN

June 17, 1972. [P] Five men in suits and surgical gloves are arrested inside the Democratic National Committee headquarters at the Watergate complex in Washington. [P]

Within days, the White House shrugs it off. [p] A “third-rate burglary.” [p] Campaign noise. [p] Nothing that touched the President. [P]

The President said there was no White House connection. [p] Later, the record would expose gaps — erased stretches of tape that experts could measure but never restore. [P]

Two years later, Richard Nixon resigns on national television — the first U.S. president to leave office that way. [P]

The story isn’t that a break-in happened. [p] It’s how a cover-up turned a dismissed crime into a constitutional reckoning. [p] And how Agency pasts in the break-in crew would feed a darker cartoon — one this channel will refuse — while the documents show something else: a cover that tried to pull the CIA into the White House’s defense. [P]

---

## CHANNEL INTRO (locked — only topic changes)

[P] Welcome to From Fiction to Fact, where each episode brings you the truth behind a story that was once dismissed as fiction. [p] In this week’s episode, we go from Fiction to Fact on Watergate — the “third-rate burglary.” [P]

---

## ACT 1 — THE FICTION

[P] The durable public fiction was simple: this was small-time crime. [p] Partisan theater. [p] A bungled break-in with no meaningful link to the President of the United States. [P]

On the night of June 16 into June 17, 1972, five men were caught inside DNC offices at the Watergate. [p] Security guard Frank Wills noticed tape on a door latch and called the police. [p] The National Archives still holds the log that marks that night. [P]

The next day, the *Washington Post* reported the arrests. [p] A day after that, Bob Woodward and Carl Bernstein reported that one of the five — James McCord — was a salaried security coordinator for President Nixon’s re-election committee, the Committee for the Re-Election of the President. [p] McCord was also a former Central Intelligence Agency officer. [p] Another name soon tied to the burglary team: E. Howard Hunt — likewise with a CIA past on the public record. [P]

Still, the White House line held. [p] Press Secretary Ron Ziegler called it a “third-rate burglary” — language preserved in the Ford Library’s Watergate Files. [p] On June 22, Nixon denied White House involvement at a press conference. [p] CRP and former Attorney General John Mitchell denied the burglars operated on the committee’s behalf. [P]

Those Agency résumés would make people ask whether the CIA itself had engineered Nixon’s fall. [p] Hold that question. [p] This channel will not treat a CIA plot to oust the President as fact. [p] What the documents later show is different: Agency alumni in the break-in crew, and a White House effort to use the CIA as cover against the FBI — cover-up facts, not a coup. [P]

The 1972 campaign was already roaring toward a landslide. [p] Many outlets and many voters treated Watergate as limited noise — overblown, temporary, not a presidency-ending crisis. [P]

That was the fiction this episode has to name carefully: not “no crime occurred,” but “this crime doesn’t reach the Oval Office.” [p] Small. [p] Contained. [p] Third-rate. [P]

---

## ACT 2 — THE PUSHBACK

[P] The minimization did not go unchallenged. [P]

Investigative reporting at the *Washington Post* and elsewhere kept tracing cash, connections, and “dirty tricks.” [p] Judge John Sirica, overseeing the burglary trial in early 1973, made clear he did not believe the story stopped with the men in the dock. [P]

Then, on March 19, 1973, James McCord sent a letter to Sirica. [p] He alleged pressure to plead guilty and remain silent — and perjury by others. [p] He also stated that the Watergate operation was not a CIA operation. [p] That letter cracked the sealed narrative of lone burglars acting alone. [P]

From May 1973, the Senate Select Committee on Presidential Campaign Activities — the Watergate Committee under Senator Sam Ervin — held televised hearings. [p] The Senate Historical Office’s record of that investigation, and the committee’s later final report, document how public testimony turned a campaign-season story into a national constitutional drama. [P]

White House counsel John Dean testified to a cover-up. [p] Alexander Butterfield disclosed that a White House taping system had been recording presidential conversations. [p] Suddenly the question was not only who broke into the DNC — but what the President had said, on tape, about stopping the investigation. [P]

In October 1973 came the Saturday Night Massacre: the firing of special prosecutor Archibald Cox after the Attorney General and his deputy resigned rather than carry out the order. [p] Public trust collapsed further. [p] The House Judiciary Committee opened an impeachment inquiry. [P]

Pushback, here, was not a single scoop. [p] It was press persistence, judicial skepticism, congressional investigation, and prosecutorial pressure — working in parallel against a White House that had called the crime third-rate. [P]

---

## ACT 3 — THE REVEAL

[P] The reveal is the cover-up — documented, not cartooned. [P]

On July 24, 1974, the Supreme Court ruled unanimously in *United States v. Nixon* that the President had to surrender the tapes. [p] Executive privilege was not absolute. [p] The Court ordered the evidence out. [P]

Days later — July 27 through July 30, 1974 — the House Judiciary Committee adopted three articles of impeachment. [p] Article I centered on obstruction of justice. [p] Those articles were adopted by the Committee. [p] They never reached a full House floor impeachment vote. [P] Nixon resigned first. [P]

The tape that collapsed remaining congressional support was the June 23, 1972 conversation between Nixon and H.R. Haldeman — the so-called “smoking gun.” [p] On that recording, released after the Court’s order, Nixon and Haldeman discuss using the CIA to curb the FBI’s Watergate probe. [p] That is presidential involvement in obstructing the investigation — proven on the President’s own voice, preserved at the Nixon Library’s Watergate trial tapes exhibit. [P]

Another key recording from March 21, 1973 — Dean’s “cancer on the presidency” warning — shows the cover-up discussed inside the White House as an ongoing problem, not a rumor from outside. [P]

What this channel will **not** treat as proven: that Nixon personally ordered the June 17 break-in itself. [p] Historians still debate the exact authorization chain for the Gemstone / DNC entries — who approved what version of G. Gordon Liddy’s plan, and how far Mitchell’s role ran. [p] The documented presidential culpability that ended the presidency centers on the **cover-up** — obstruction — proven especially by the tapes and the impeachment articles. [p] Not a neat “he planned the burglary” cartoon. [P]

And Mark Felt — later confirmed as the *Post* source known as “Deep Throat” — was important. [p] He was not the sole or magical cause. [p] The fall of the presidency required institutions: reporters, prosecutors, the Senate committee, House Judiciary, and the Supreme Court. [p] Credit the spine, not a single whisper. [P]

On August 8, 1974, Nixon addressed the nation and announced he would resign. [p] The resignation letter took effect at noon on August 9. [p] The National Archives still holds that letter. [p] Gerald Ford became president. [P]

---

## MID-ROLL BEAT

[P] If this channel is useful — stories that were called noise until the record opened — subscribe. [p] We don’t chase every rumor. [p] We follow the spine: what was claimed, who dismissed it, what the primary record later showed. [P]

---

## ACT 4 — THE AFTERMATH

[P] What is true now? [P]

Five men were arrested inside the DNC at the Watergate on June 17, 1972. [p] | Early White House framing minimized it as a third-rate burglary. [p] | Reporting, hearings, and courts established a presidential cover-up. [p] | The smoking-gun tape showed Nixon directing an effort to use the CIA against the FBI probe. [p] | The Supreme Court forced the tapes out. [p] | House Judiciary adopted impeachment articles. [p] | Nixon resigned before a full House vote. [P]

Ford later pardoned Nixon — September 8, 1974. [p] That pardon is a separate political fight; this episode does not hang the Watergate arc on it. [p] Campaign-finance and ethics reforms followed in the mid-1970s. [p] “Watergate” became the template for naming political scandals — every “-gate” since. [P]

What remains uncertain — and this channel says so plainly: [P]

Those gaps we flagged early include the famous 18½-minute erasure — a June 20, 1972 Nixon–Haldeman conversation with multiple erasures. [p] The full contents are **unknown**. [p] Experts documented the erasures. [p] They did not recover the missing words. [P] We do not invent them. [P]

The precise boundaries of Nixon’s knowledge *before* June 23, 1972, versus cover-up decisions after, are constrained by the tapes and testimony — not by later fan fiction. [p] Exact Gemstone authorization details are still debated among historians. [P]

What we refuse: Deep State lore that Watergate was a CIA setup to remove Nixon; body-double conspiracies; framed-by-the-Establishment fanfic sold as fact. [p] McCord’s letter said the operation was not CIA. [p] The primary record shows a cover-up collapsing under investigation — not a cartoon coup. [P]

[P] Fiction said: third-rate burglary, no presidential link that mattered. [P]

[P] The files said: a cover-up on tape — and a resignation. [P]

---

## CTA / CLOSE

[P] This was From Fiction to Fact — Episode Three. [P]

We don’t ask you to believe every rumor. [p] We ask you to follow the paper. [p] When the cartoon outruns the documents, we refuse the leap. [p] When the archives, the courts, and the committees speak, we say what they show — and stop where they stop. [P]

If you want the next case — another claim that lived as dismissal until the record opened — like and subscribe. [p] Tell us in the comments which dismissed story you want examined next. [p] Sources for this episode are in the description. [P]

See you in the next episode.

---

## Cut notes (v3 Christopher Neural bake)

1. **Chunk strategy:** Bake sentence-by-sentence or short paragraph. Use sentence-end `[p]` / section `[P]` / Aftermath `|` as split points. Let Christopher speak through em-dashes and appositives without mid-clause chops.
2. **Voice settings:** `en-US-ChristopherNeural`, pitch **−8Hz**. Rate: **unlocked** — try **−5%** first for naturalness (Daniel: less slow/choppy). Do **not** lock at −10% on this bake unless the −5% pass still feels wrong and Daniel asks to revert.
3. **Stitch:** Map markers to the **v3 legend durations** (`[p]` ~800ms, `[P]` ~1350ms). Longer gaps *between* sentences; almost no mid-clause silence.
4. **Post:** Light EQ + light de-chop after stitch (house pass). Do not time-stretch spoken words to invent pauses — use the markup silences.
5. **Wording:** Do not edit spoken text. If a bake glitch needs a re-take, re-feed the identical strip-verified string for that chunk only.
6. **Out path suggestion:** `assembly/ep03/vo/ep03-full-christopher-v1.1-timing-v3.mp3` (+ `.vtt` + `-text.txt`) — leave prior v1/v2 timing bakes untouched until Daniel/Cut swap.
7. **Verifier:** Wording frozen = joint PASSed v1.1 (`reviews/ep03-watergate-joint-v1.1-verifier.md`) — **no re-gate** for this timing-only pass. Clear for VO-timing → Cut. **No Distro.**

## Marker counts (this file)

- `[br]` = 0
- `[p]` = 72
- `[P]` = 53
- `\|` = 6
- Spoken word count (stripped) = 1518

## Self-check

- [x] Spoken text after stripping markers == `ep03-watergate-v1.1-narration-only.md` spoken body
- [x] No claim / fence / wording edits
- [x] Legend durations match Daniel preferred (`[p]` 700–900ms, `[P]` 1.2–1.5s); mid-clause `[br]` stripped
- [x] Rate unlocked for Cut −5% naturalness try; pitch −8Hz
- [x] Status VO-TIMING v3 for Cut only — not for publish / Distro
- [x] Supersedes YT v1 and v2 timing files for this bake path
