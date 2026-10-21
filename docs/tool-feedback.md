# Organizer tool-feedback worksheet

Use this editable worksheet for the Devpost feedback field. The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) require feedback on the Nebius and NVIDIA tools used. The facts below come from the repository's documented test; experience ratings and first-person judgments are **ACTION REQUIRED** for the entrant to supply. Do not paste an API key, account identifier, private log, or unverified performance claim into the submission.

## What the tools were used for

**Documented fact:** AXIOM's Nebius Token Factory provider requested a structured reasoning reply from `nvidia/nemotron-3-super-120b-a12b`. One authorized live smoke request returned the same response model and a validated reply on 19 October 2026. The canonical research loop can select that provider by configuration; the recorded end-to-end dashboard demo uses Echo offline. Nebius AI Cloud GPU execution exists as experimental adapter code but has not been verified with a real job. No other NVIDIA or Nebius tool is documented as used in a live AXIOM run.

**ACTION REQUIRED:** state which tools you personally used beyond the documented smoke request, if any, and for what task. Do not say AI Cloud or GPU compute was used unless separately verified.

## What worked well

**Documented observation:** The configured Token Factory endpoint returned one response identifying the requested Nemotron model, and AXIOM parsed and validated the structured result. The offline Echo path and automated tests ran without a live key.

**ACTION REQUIRED — your assessment:** Which parts of setup, model access, response format, documentation, or iteration helped you? Give a concrete example you experienced. Avoid claiming measured speed or reliability from a single request.

## What needs improvement

**ACTION REQUIRED — your assessment:** Describe any friction you personally encountered with access, onboarding, model availability, response formatting, errors, documentation, pricing visibility, or deployment. Include a reproducible example if one exists. No provider defect is established by the repository record.

## Onboarding and first successful request

**Documented sequence:** The team configured the existing Nebius provider for the Token Factory v1 endpoint and Nemotron 3 Super. Earlier local checks lacked an authorized key and exited before a request. With an authorized environment credential, the opt-in command made one request and validated its response. The key was not committed or printed by the command.

**ACTION REQUIRED — your experience:** Explain how you obtained access, whether onboarding instructions were clear, how long the first working request took, and what you would change. Do not disclose the credential or account details.

## Would you use the tools again, and why?

**ACTION REQUIRED — personal judgment:** Answer yes, no, or conditional, and give a reason based on your experience. Distinguish the demonstrated structured-reasoning use from future unverified GPU or optimization plans.

## Final review before pasting into Devpost

- [ ] All first-person statements are yours and describe what actually happened.
- [ ] Every named NVIDIA/Nebius tool was used as described, or is clearly labelled as planned or unverified.
- [ ] No secret, private account detail, invented performance number, or unsupported production claim appears.
