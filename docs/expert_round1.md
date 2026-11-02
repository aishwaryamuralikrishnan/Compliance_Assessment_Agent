# Compliance Assistant · expert review, round 1

About fifteen minutes. The assistant gives a product team an article-cited first assessment of a planned feature
against the GDPR and the EU AI Act; the DPO decides what goes on record. We are evaluating it against twenty
feature descriptions with expected answers written by the author. Round 1 asks three things of you: whether the
list of situations we cover is the right one, whether five expected answers are right, and four questions on the
rule we use to score a finding. Agree / disagree and one line why is all that is needed; nothing has to be
written from scratch.

For each item there is a line `Your view:` to fill in.

> **Status (27 Oct).** No reply from the human expert yet, so this pack was put to Gemini 3.1 (Argon 4, medium
> thinking) acting as a DPO, and its answers were applied as a *preliminary* review: the domains below (D3
> narrowed to the fintech uses, FRIA added, D5 keeps Annex III point 4), three pairs added to B (fraud vs
> creditworthiness, 1:1 biometric verification vs identification, processor vs controller-vendor), FRIA findings
> added to A-003 and A-004, and on D: no severity tolerance, a citation level per finding (paragraph where the
> article is an umbrella), extras split into wrong and merely extra, mixed findings scored by atomic point. Two
> of its points were set aside as outside the corpus or the scope: ePrivacy (not ingested) and Art. 5(1)(f)
> emotion recognition (workplace and education only). Section E, written with the other fifteen cases, was
> answered the same day: banned AI uses taken out of the set (two cases replaced), a FRIA demanded of a private
> company scored as wrong, the refund Blocker confirmed. Every row keeps `reviewed_by: "gemini (preliminary)"`
> until the human expert has answered; her answers replace Gemini's wherever the two differ. The questions in D
> are kept as they were asked, so that she answers the same questions. Round 2 (the other fifteen cases,
> `docs/expert_round2.md`) was reviewed the same way the same day; its status note lists what changed.

## A. The situations we cover

The twenty end-to-end cases are spread over these areas (three or four each). Are these the situations a
fintech product team actually brings to a DPO? What is missing, what can go?

| Id | Area | The law that decides | cases |
|---|---|---|---|
| D1 | Automated decisions and profiling | GDPR Art. 22, Rec. 71, Art. 4(4); Art. 35(3)(a) | 3 |
| D2 | Data sharing and international transfers | GDPR Art. 44–49, Art. 28 (processors), Art. 6(4) | 3 |
| D3 | A new AI component that is high-risk (customer-facing fintech: creditworthiness, Annex III point 5(b); remote biometric identification, point 1) *[narrowed on the preliminary review; hiring lives in D5 only]* | AI Act Art. 6, Annex III points 1 and 5, Art. 25 (deployer becomes provider), Art. 26 (deployer), Art. 27 (FRIA) | 3 |
| D4 | A new AI component that is not high-risk | AI Act Art. 50 (transparency), Art. 5 (not prohibited), Art. 6(3) | 2 |
| D5 | HR and hiring | AI Act Annex III point 4, GDPR Art. 88, Art. 22 | 3 |
| D6 | Special-category data (including data the feature infers) *[AI Act Art. 5 removed on the preliminary review of section E: banned uses are out of the set]* | GDPR Art. 9, Art. 35(3)(b), Art. 21 | 3 |
| D7 | Plainly low-risk features (the right answer is "Proceed") *[two cases since round 2; the third became the D8 case]* | GDPR Art. 5, Art. 6(1)(f), Art. 13 | 2 |
| D8 | Data subject rights and retention *[added on round 2: a "Delete my account" button against retention duties]* | GDPR Art. 17(3)(b), Art. 18; AI Act Art. 26(6) | 1 |

Your view:

## B. Pairs that are easy to confuse

Some cases come in pairs: two situations that sound alike but where the law gives different answers. We use
them to check that the assistant tells them apart. Are these pairs real, and which others would you add?

- A solely automated decision (Art. 22 bites) against the same feature with a human taking every decision.
- An AI component that is high-risk (creditworthiness, Annex III point 5) against one that is not (an FAQ chatbot).
- A transfer to a vendor certified under the EU-US Data Privacy Framework (Art. 45) against one to a vendor
  with no certification (Art. 46 safeguards needed).
- A low-risk feature that uses the vocabulary of a risky one (e.g. "tracking", "profile") but changes nothing.
- *Added on the preliminary review:* credit scoring (Annex III point 5(b), high-risk) against fraud detection on
  the same data (expressly excluded from point 5(b), not high-risk); a one-to-one face check at account opening
  (verification, excluded from Annex III point 1) against matching every branch visitor to a watch-list
  (identification, high-risk, plus GDPR Art. 9); a vendor that processes only on our instructions (a processor,
  Art. 28) against one whose contract lets it train and sell its own models on our data (a controller for that
  use, Art. 28(10), Art. 6(4)).
- For short questions: Art. 22 automated decisions against Art. 6(1)(f) legitimate interests; Art. 35 DPIA
  against Art. 36 prior consultation; AI Act Art. 5 prohibited practices against Annex III high-risk (social
  scoring against creditworthiness); Art. 17 erasure against Art. 18 restriction.

Your view:

## C. Five expected answers

For each case: the feature as the product manager would write it, then what we expect the assistant to say.
"Blocker" = must change before build; "Required" = an obligation to fulfil; "Covered" = already handled (for
example by a fact about the organisation). Please mark agree / disagree per case and say what you would change.

### A-001 · a plainly low-risk feature

> We want to add a 'recently viewed products' strip on the homepage. The list lives in the customer's own
> account, holds the last twenty items, is deleted after thirty days, is shown only to that customer and is not
> used for anything else. Our privacy notice already says we keep browsing activity inside the account.

Expected: **Proceed**, low risk, not high-risk AI, no DPIA. Findings: Covered, data minimisation and storage
limitation are met by design (Art. 5(1)(c), (e)); Covered, the customer is already informed (Art. 13).

Your view:

### A-002 · a transfer the organisation's facts do not cover

> We're moving all customer support ticket data (names, order numbers, the text of the complaints) to a new
> helpdesk vendor whose servers are in India. The vendor will host and process the tickets for us. The contract
> is still being negotiated.

Expected: **Proceed with conditions**, medium risk, not high-risk AI, no DPIA. Findings: Required, a transfer to
a third country without an adequacy decision needs appropriate safeguards (Art. 46); Required, the vendor is a
processor and needs an Art. 28 contract; Required, customers must be told about the transfer (Art. 13).

Your view:

### A-003 · automated credit scoring, fully automatic

> We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device
> fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US
> fraud-prevention vendor.

(The organisation's memory holds the fact that this vendor is certified under the EU-US Data Privacy Framework.)

Expected: **Do not build as described**, high risk, high-risk AI, DPIA required. Findings: Blocker, a solely
automated decision with legal or similar effect needs human intervention and a way to contest (Art. 22(1),
22(3)); Required, DPIA before processing (Art. 35(3)(a)); Required, creditworthiness scoring is a high-risk AI
system, provider or deployer obligations apply (Annex III point 5, Art. 6(2)); Required, a deployer of a credit
scoring system owes a fundamental-rights impact assessment before first use (AI Act Art. 27) *[added on the
preliminary review]*; Required, browsing behaviour as an input needs its own basis and minimisation, drop it or
justify it (Art. 5(1)(c), Art. 6); Covered, the transfer to the US vendor, by the DPF certification (Art. 45).

Your view:

### A-004 · the same scoring with a human taking the decision

> We're adding credit scoring to our buy-now-pay-later checkout using transaction history and device data. The
> score only flags an order; a credit analyst reviews every flagged order and takes the decision, and the
> customer is told how to appeal. Scores stay in-house.

Expected: **Proceed with conditions**, high risk, high-risk AI, DPIA required. Findings: Covered, a real human
decision takes it outside the Art. 22(1) prohibition (the review must be meaningful); Required, DPIA before
processing (Art. 35(3)(a)); Required, creditworthiness scoring is still a high-risk AI system, human oversight
does not remove the classification (Annex III point 5, Art. 6(2)); Required, a fundamental-rights impact
assessment before first use (AI Act Art. 27) *[added on the preliminary review]*.

Your view:

### A-005 · an FAQ chatbot that takes no decisions

> A chatbot on our help page answers order-status and returns questions from our FAQ. It reads the order number
> the customer types, shows the status, and hands over to a human agent whenever the customer asks or the
> question is not in the FAQ. It takes no decisions about customers.

Expected: **Proceed with conditions**, low risk, not high-risk AI, no DPIA. Findings: Required, users must be
told they are interacting with an AI system (AI Act Art. 50(1)); Covered, not a high-risk AI system (none of the
Annex III uses, no decisions); Required, order numbers and chat text are personal data, say how long transcripts
are kept (Art. 5(1)(e), Art. 13).

Your view:

## D. Four questions on how a finding is scored

A finding of the assistant counts as matching an expected finding when it makes the same legal point, cites the
expected provision and carries the expected severity. Each question below states the rule as it was when the
pack was written, and, in italics, the preliminary answer applied on 27 Oct, which is the rule in force now. The
questions are kept as first asked so that your answer can be set against the preliminary one.

1. Severity: as first written, for a finding we expect as "Required" we accepted "Blocker" as well (one level
   apart), and nothing else for "Blocker" and "Covered". Is one level of tolerance acceptable to a practitioner,
   or is one level already an error?

   *Preliminary answer, in force: no tolerance. A Blocker for an expected Required is an error, because the two
   call for different actions from the team (stop and redesign, against fulfil an obligation before launch); it
   counts as missed, on a separate line "right point, wrong severity".*

   Your view:

2. Citation: is the article enough ("Art. 22"), or does a DPO expect the paragraph ("Art. 22(1)")?

   *Preliminary answer, in force: the article is enough except for the umbrella provisions (GDPR Art. 5, 6, 9,
   AI Act Art. 5, Annex III), where the paragraph or point is required because a bare article number does not
   show which rule is meant.*

   Your view:

3. Extras: the assistant sometimes adds findings beyond the ones we expect. Which kinds of additional finding
   would you consider *wrong* (an obligation that does not exist, a provision cited for something it does not
   say) rather than merely extra?

   *Preliminary answer, in force: wrong = statutory fabrication, contextual blindness (demanding what the
   description says is done) and false escalation (Art. 36 where a DPIA suffices, a non-AI feature called
   high-risk, a Blocker for paperwork); merely extra = evergreen duties (Art. 30, 32, 25, AI Act Art. 4, a
   lawful-basis note) and any correct point we did not list.*

   Your view:

4. A mixed finding: on A-003 the assistant once wrote, as one finding labelled "Required", that the US transfer
   is covered by the DPF certification *and* that a processor agreement with the vendor is still needed. We
   expected "Covered" for the transfer. Should such a combined finding count as Covered (the transfer point is
   right), as Required (there is still something to do), or should the two points be scored separately?

   *Preliminary answer, in force: scored separately, by atomic point; the assistant's prompt now asks for one
   severity per finding.*

   Your view:

## E. Three choices made while writing the other fifteen cases (preliminary answers applied; please confirm or correct)

1. **Is a banned AI use also "high-risk"?** Two cases describe AI uses the AI Act bans outright: reading
   employees' emotions from their voice at work (Art. 5(1)(f)) and guessing customers' ethnicity or religion from
   their photo (Art. 5(1)(g)). The assistant has a yes/no flag "high-risk AI". We set it to **yes** for these,
   reasoning that a banned use is worse than high-risk, not less, and that Annex III point 1 lists emotion
   recognition and biometric categorisation anyway. The real answer is the "Blocker: this is prohibited". Would
   you set the flag to yes or no for a banned use?

   *Preliminary answer, applied: neither. "Prohibited" (Art. 5) and "high-risk" (Art. 6, Annex III) are
   separate boxes; Annex III point 1 applies only "in so far as their use is permitted", so a banned use is not
   on the high-risk list, and a yes/no flag cannot say "prohibited". The two banned-use cases were taken out of
   the set and replaced by lawful cases in the same areas (A-015: shift allocation and performance flags at a
   call centre; A-018: religion inferred from names and transaction timing). The prohibitions stay tested by the
   short-question sets.*

   Your view:

2. **A FRIA asked of a private company.** The fundamental-rights impact assessment (AI Act Art. 27) is owed by
   public bodies, by private firms providing public services, and by anyone using AI for credit scoring or
   life/health insurance pricing. A private fintech using AI to screen job applicants, or to recognise faces in
   its branches, does not owe one. If the assistant nevertheless says "do a FRIA", we count that as *merely
   extra* (harmless advice), not as *wrong*. Agree, or is demanding an assessment the law does not require an
   error?

   *Preliminary answer, applied: an error. A FRIA demanded as an obligation ("Required", Art. 27) of a private
   employer or bank is false escalation, the AI Act twin of demanding Art. 36 prior consultation where a DPIA
   suffices; the judge counts it as wrong. A FRIA mentioned as optional good practice is merely extra.*

   Your view:

3. **Is an automated refund refusal an Art. 22 decision?** Case A-006: a chatbot alone approves or refuses
   refund claims up to 500 euros; refusals are final and there is no person to turn to. Art. 22 covers decisions
   made only by a machine that have a legal effect or "similarly significantly affect" the person. We treated
   losing up to 500 euros with no appeal as significant enough, so the expected answer is a Blocker (add a human
   route and a way to contest). Would a DPO agree, or is a refund refusal too small for Art. 22, in which case
   the case should expect "Required" (good practice) or nothing at all on Art. 22?

   *Preliminary answer, applied: a DPO agrees, Blocker. Refusing a refund claim denies a contractual right, which
   is a legal effect under Art. 22 whatever the amount; losing up to 500 euros with no appeal is significant
   besides. The automation is allowed under the contract exception only with the Art. 22(3) safeguards.*

   Your view:

Thank you. Round 2, if you are willing, is the remaining fifteen cases in a spreadsheet, agree / disagree per
row, plus two or three hiring or HR features from your own field with what you would expect.
