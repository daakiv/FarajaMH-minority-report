# FarajaMH Minority Report

A guided human-in-the-loop review tool for culturally grounded mental-health expressions in Kiswahili, Sheng and code-switched language. Several language models interpret each expression separately; trained reviewers decide the meaning, assess safety and sign off terminology matches.

It extends [The Minority Report](https://github.com/codata/the-minority-report) by Slava Tykhonov (CODATA). When models disagree, the less-supported reading, the *minority report*, stays visible for the reviewer instead of being discarded.

![FarajaMH Minority Report workflow](docs/figures/farajamh-workflow-v10.png)

## How it works

1. **Utterance and context:** the original wording, language and setting are kept.
2. **Identify expressions:** each expression is reviewed in its full context.
3. **Model interpretations:** each model reads the expression independently, before seeing the dictionary.
4. **Dictionary evidence:** a versioned idiom library adds evidence. It is not a vote.
5. **Compare and route:** disagreements, safety flags and cases missing who, negation or time always go to review. A reproducible 10% sample of agreed cases is also reviewed; the rest are marked "Agreed, not sampled" and can still be reviewed by choice.
6. **Human review:** a reviewer approves the meaning. Safety is assessed separately.
7. **Terminology lookup:** candidates from MFOEM, MFOMD and SNOMED CT are signed off as exact, close or related matches, or recorded as gaps.
8. **Record and outputs:** every decision is versioned, with SSSOM and Croissant exports.

**Dictionary evidence ≠ model vote. Model agreement ≠ correctness. Concept mapping ≠ diagnosis.**

## Features

**Review**
- Guided step-by-step screen, from new expression to terminology sign-off, with Back/Next and a checklist of what is still missing.
- Side-by-side model readings with literal translation, main and alternative readings, safety suggestion and self-reported confidence.
- Minority and tied readings stay visible; any reading can be used as the starting point for the approved meaning.
- Meaning decisions: approve one, keep several, ask for context, leave unresolved, request a second opinion, or reject.
- Separate safety finding (no concern, uncertain, concern flagged) with recorded checks and a required note when there is concern.

**Terminology**
- Live lookup in MFOEM, MFOMD and SNOMED CT using the reviewer's search terms, with each candidate's domain shown.
- Sign-off as exact, close, related, broader or narrower match, a recorded gap, or deferral; failed searches can be retried.
- Unsaved choices are kept while moving between steps.

**Models and routing**
- Model switch: choose a small local or large hosted model set for each new expression; each case records the set that read it, so results are never mixed.
- Disagreements and safety signals always go to review; a reproducible 10% sample of agreed cases is reviewed too.
- Model scorecard: how each model compares with reviewer-approved meanings (readings used, minority readings used, ratings, confidence when right vs wrong, run time), shown per model set. Counts cover approved synthetic cases only and are not accuracy.

**Record**
- Every decision is versioned with who, when and why; nothing is overwritten.
- Exports to SSSOM and Croissant; a pilot report with metrics and the audit log.
- Runs locally: SQLite database, and no data leaves the machine unless a hosted model set is chosen.

## Quick start

Requires Python 3.11 or later (tested on 3.13).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q
```

Try it offline with built-in test responses (no models or network needed):

```sh
.venv/bin/python -m farajamh --config config.yaml init
.venv/bin/python -m farajamh --config config.yaml run examples/source.json
FARAJA_DEMO_KE_TOKEN=choose-a-long-token \
  .venv/bin/python -m farajamh --config config.yaml review --serve --port 8765
```

Open http://127.0.0.1:8765/ and sign in with the token you chose.

## Configurations

| File | Models | Terminology | Use |
|---|---|---|---|
| `config.yaml` | Built-in test responses | Fictional test concepts | Offline demo and tests |
| `config.live-test.yaml` | Local [Ollama](https://ollama.com) models (small set); template for a hosted large set | Live MFOEM, MFOMD, SNOMED CT (via EBI OLS) | Synthetic test runs on real models |

Data is stored in `work/` (SQLite database and exports), which is not committed.

## Model sets (small and large switch)

Models are grouped into named sets in `config.live-test.yaml`. Each case is read by one set only, and the comparison and scorecard never mix sets.

| Set | Models | Status |
|---|---|---|
| `small` | gemma3:12b, qwen2.5:7b, llama3.1:8b (local, via Ollama) | In use |
| `large` | Hosted models through an OpenAI-compatible API | Template ready; TBD |

Choose the set on the **New expression** form, or with `--model-set` on the command line:

```sh
.venv/bin/python -m farajamh --config config.live-test.yaml run case.json --model-set small
```

To turn on the large set, uncomment it in the config, add the provider's address to `network.allowed_origins`, and set the API key in the terminal. Keys are never stored in files:

```sh
export FARAJA_LLM_API_KEY=your-key
```

A hosted set sends the utterance to an external service, so it is for synthetic data only. See [Setup](docs/SETUP.md).

## Repository layout

| Folder | Contents |
|---|---|
| `farajamh/` | Application code, prompts, schemas and the review screen |
| `tests/` | Automated tests |
| `tools/` | Scripts for building test data and validation |
| `pilot/`, `examples/` | Synthetic test cases |
| `docs/` | Design, workflow and setup documentation |
| `evidence/` | Results from earlier synthetic pilot runs |

## Documentation

- [Workflow](docs/WORKFLOW.md): the eight-step process in detail
- [Setup](docs/SETUP.md): models, model sets, terminology and run modes
- [Commands](docs/COMMANDS.md): every command-line option, including the scorecard
- [Alignment](docs/ALIGNMENT.md): what is built and what is still missing

## Planned

- Connect the large hosted model .
- Recognise model readings that mean the same thing in different words, so agreed cases can be sampled (with live models, readings are currently never grouped).
- Batch evaluation of model readings against reviewer-approved meanings, possibly with Gooey.AI.

## Licence

TBD
