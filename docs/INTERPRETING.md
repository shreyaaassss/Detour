# Typed reports: how they are read

A dispatcher can describe a change in their own words ("the Kothrud to Aundh road is slow until 4 pm, it adds
25 minutes") instead of filling in a form. The result is only ever a **proposal**.

```
words -> reader(s) -> checks -> preview (what was understood + the effect) -> dispatcher applies -> audit log
```

## Two readers

- **The rule-based reader** (always on, no AI, no network) understands plain phrasings of the three disruptions.
  It is strict: it asks for what is missing instead of assuming it.
- **The language model** (OpenAI, only if `OPENAI_API_KEY` is set; turn it off with `DETOUR_LLM=off`; choose the
  model with `OPENAI_MODEL`, default `gpt-4o-mini`) reads wordings the rules cannot, such as "Ravi's van just died".
  It fills in a fixed form. It is never asked to make a decision.

Both always run. If the model is unavailable (no key, network, timeout, bad output) the rule reader takes over and
the screen says so. If both read the text and **disagree**, the strict rule reader wins and the model's reading is shown
as a warning. If only the model can read it, its answer is used, but only after the checks below.

## What is checked, whatever the model says

- Every place must be on the known list **and be named in the dispatcher's text**. A model that maps "the airport
  road" to a real place id is refused. An unknown place is rejected with the list of known ones, never guessed.
- A vehicle must exist and be named (by id or driver) in the text, and must not have already failed.
- A time must be a real clock time. Any time or number the model returns that cannot be read out of the text is flagged.
- The finished disruption passes the same validation as one typed into the form, then the same independent
  validator when it is previewed.
- Text inside the report is treated as data. The model can only fill in the form, so "ignore your instructions"
  has nothing to act on.
- Nothing applies until the dispatcher reviews the plain-language reading and the effect, and applies it. The audit
  log records the words, the method (rules or model name), what was understood, and who confirmed it.

## Privacy

With the model on, the report text and the **fictional** place and vehicle names of the scenario are sent to OpenAI.
No other data is. Use `DETOUR_LLM=off` to keep everything local.

## API

`POST /disruptions/parse {"text": "...", "source": "text" | "voice"}` returns the reading and a preview, or a 422
`cannot_interpret` with the reasons and the known places. `GET /interpreter` says which reader is active. Voice
reports (Phase 8) use the same endpoint with `source: "voice"`.
