# ADR 0001: The default terminal prompter

**Status:** Accepted
**Related:** [#15](https://github.com/mikimn/InteractiveArgparse/issues/15), [#11](https://github.com/mikimn/InteractiveArgparse/issues/11)

## Context

`PyInquirerPrompter` (registered as `"pyinquirer"`) is the prompter `InteractiveArgumentParser` falls back to whenever no `prompter=` is given. It wraps [PyInquirer](https://github.com/CITGuru/PyInquirer), whose last release was `1.0.3` in 2018. PyInquirer pins `prompt_toolkit<2.0`, and `prompt_toolkit==1.0.14` imports ABCs directly from `collections`, which were removed from that module in Python 3.10 — this project already carries a `collections.Mapping = collections.abc.Mapping` compat shim (`PyInquirerPrompter._load_prompt`) just to keep it importable. Nothing guarantees that shim keeps working on future Python versions, and PyInquirer itself receives no fixes if it stops.

This ADR compares the realistic options for the *default* prompter and makes a call, per #15's definition of done. It intentionally only decides the default; any registered prompter (`"pyinquirer"`, `"rich"`, `"web"`, or a custom one) remains explicitly selectable regardless of what the default is.

## Options considered

| | **PyInquirer** (status quo) | **RichPrompter** ([#11](https://github.com/mikimn/InteractiveArgparse/issues/11)) | **`questionary`** | **`InquirerPy`** |
| --- | --- | --- | --- | --- |
| Upstream maintenance | Unmaintained since 2018 (v1.0.3) | N/A — `rich` itself is actively maintained (weekly-ish releases, large user base via `pip`, `textual`, etc.) | Actively maintained; regular releases, modern `prompt_toolkit` support | Actively maintained fork/reimagining of PyInquirer's API, modern `prompt_toolkit` support |
| New dependency for this project | none (already required) | **none** — `rich` is already pinned in `requirements.txt` | new: `questionary` (pulls in a current `prompt_toolkit`) | new: `InquirerPy` (pulls in a current `prompt_toolkit`, `pfzy`) |
| Python 3.10+ compatibility | Needs the `collections.Mapping` shim; fragile, upstream won't fix regressions | Native — no ABC-relocation issues | Native | Native |
| `TEXT` / `INT` / `FLOAT` | `input` type, no built-in validation (source of [#12](https://github.com/mikimn/InteractiveArgparse/issues/12)) | `Prompt` / `IntPrompt` / `FloatPrompt` — validates and re-prompts *before* this library's own `cast` even runs | `text`, validated via `Validator` if supplied | `input`/`number`, similar validator hook |
| `CONFIRM` | `confirm` type | `Confirm` | `confirm` | `confirm` |
| `SINGLE_CHOICE` | `list` type | `Prompt(choices=...)` — accepts free text matching a choice, not an arrow-key menu | `select` — real arrow-key menu | `select` — real arrow-key menu |
| `MULTI_CHOICE` | `checkbox` — real multi-select menu | **No native multi-select** — falls back to a free-text field split on commas/whitespace (see `RichPrompter._to_rich_prompt`) | `checkbox` — real multi-select menu | `checkbox` — real multi-select menu |
| Visual polish | Basic | Basic, consistent with `rich`'s styling | Polished, closest to the original PyInquirer/Inquirer.js look | Polished, closest to the original PyInquirer/Inquirer.js look |

**Feature parity verdict:** `questionary` and `InquirerPy` are the only two with full parity, including a real `MULTI_CHOICE` checkbox menu — because, like PyInquirer itself, they're built for exactly this job. `RichPrompter` trades that one gap for zero new dependencies, better validation on scalar types, and an actively maintained foundation.

## Recommendation

**Make `RichPrompter` the new default**, and keep `PyInquirerPrompter` registered and fully functional, but deprecated.

Rationale:
- The core problem this ADR exists to solve is "the default prompter sits on an unmaintained foundation with a fragile compat shim." `RichPrompter` fixes that with **no new dependency** — `rich` is already required by this project (currently unused elsewhere, per #11's own motivation). `questionary`/`InquirerPy` would fix the same maintenance problem while *adding* a dependency, which is a worse trade for the common case.
- `RichPrompter`'s one real gap — `MULTI_CHOICE` has no arrow-key checkbox menu — is a narrower miss than it looks: `nargs="+"` arguments are less common than plain scalar/boolean/choice arguments in typical `ArgumentParser` scripts, and `WebPrompter` already exists as a full-fidelity checkbox experience (via the `web` extra) for scripts that lean heavily on multi-select arguments.
- If a real terminal checkbox experience is needed later, `questionary` (closer to idiomatic modern Python, simpler API) is the better of the two follow-up candidates over `InquirerPy` (whose value proposition is closely replicating PyInquirer's own API, which matters less once we're not on PyInquirer's API base internally to begin with). That would ship as a new optional `Prompter` (e.g. a `questionary` extra, same pattern as `web`), not as the bundled default — tracked as a separate future issue, not part of this ADR's scope.

## Migration / deprecation path

This ADR is a decision record only — no code changes ship with it (per #15's definition of done). The plan for the follow-up implementation PR, once this decision is accepted:

1. Change `InteractiveArgumentParser._build_default_prompter()` to return `RichPrompter()` instead of `PyInquirerPrompter()` in its no-env-var-set branch. `PyInquirerPrompter` stays registered as `"pyinquirer"` and fully supported — `@interactive("pyinquirer")` and `InteractiveArgumentParser(parser, prompter=PyInquirerPrompter())` keep working exactly as before, unchanged. Only code that relies on the *bare, unconfigured* default (no `prompter=`, no `@interactive("...")` argument, no env var) would see a different terminal UI.

   **Interaction with `INTERACTIVE_ARGPARSE_PROMPTER`** ([#14](https://github.com/mikimn/InteractiveArgparse/issues/14), already shipped): `_build_default_prompter()` already checks that variable first and only falls back to the hardcoded default when it's unset - this ADR only changes what that fallback *is*, not the lookup around it. So someone who has deliberately set `INTERACTIVE_ARGPARSE_PROMPTER=pyinquirer` to pin the old default sees no change at all: the env var branch resolves `"pyinquirer"` via `Prompter.registry` exactly as it does today, regardless of what the fallback returns. Only scripts with the variable *unset* (the actual "bare default" case) are affected. This is also why "no code changes ship with this ADR" still holds: the env-var lookup itself isn't touched, only the one line inside its fallback branch, and that line ships in #23, not here.
2. Update `docs/prompters.md`'s built-in prompter table to mark `RichPrompter` as the default and `PyInquirerPrompter` as deprecated, recommending an explicit `@interactive("pyinquirer")` or `INTERACTIVE_ARGPARSE_PROMPTER=pyinquirer` for anyone who wants to keep it deliberately.
3. Update whatever tests currently assert on the *implicit* default prompter (most of this test suite already passes `prompter=FakePrompter(...)` explicitly and is unaffected) to expect `RichPrompter` instead.
4. **Next major version:** if PyInquirer becomes actually broken (the `collections.Mapping` shim stops working on a future Python release, or PyInquirer/`prompt_toolkit==1.0.14` fails to install at all), drop `PyInquirerPrompter` and the shim rather than trying to keep patching around an unmaintained dependency. Until then, it stays as a supported, explicitly-selected option — nothing forces existing callers off it.

Tracked as a follow-up implementation issue: #23.

## Consequences

- `requirements.txt`/`setup.cfg` are unaffected either way — `PyInquirer`, `prompt_toolkit`, and `rich` are all already listed; switching the default doesn't add or remove a runtime dependency.
- No new dependency, no new extra — the entire cost of accepting this ADR is the follow-up code change in #23.
