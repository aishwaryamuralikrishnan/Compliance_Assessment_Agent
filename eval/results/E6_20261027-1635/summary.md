# E6 · 2026-10-27T15:35:26+00:00

commit `6fc8bad` · database `localhost/compliance_eval` · 20 cases

models: `worker_full` = openai/gpt-6-luna · `worker_quick` = openai/gpt-6-luna · `cheap` = google/gemini-3.1-flash-lite · `judge` = anthropic/claude-haiku-5.5 · `embeddings` = openai/text-embedding-3-small · `reranker` = cohere/rerank-4-fast · `router` = typesafe/jev-router · `grader` = openai/gpt-6-luna

## E6 full assessments

| metric | result | target |
|---|---|---|
| cases that produced an assessment | 20 of 20 (1.00) | all |
| verdict accuracy · of which dangerous (expected Do not build, got Proceed) | 13 of 20 (0.65) · 0 | ≥ 0.80 · 0 |
| risk level accuracy | 13 of 20 (0.65) | reported |
| high-risk AI flag: missed of positives · false of negatives | 0 of 7 · 0 of 13 | ≤ 1 · ≤ 1 |
| DPIA flag: missed of positives · false of negatives | 2 of 14 · 0 of 6 | ≤ 1 · ≤ 1 |
| must-cite recall (verified citations, article level) | 37 of 39 (0.95) | ≥ 0.80 |
| key findings matched (judge + rubric, no severity tolerance) | 59 of 81 (0.73) · partial 10 | matched ≥ 0.75 |
| of the missed: right point and provision, wrong severity | 7 | reported |
| wrong extras (fabrication, contextual blindness, false escalation) | 2 | reported |
| must_not violations | 0 | 0 |
| faithfulness of findings (RAGAs definition, own implementation), mean | 0.851 over 20 | ≥ 0.85 |
| confusable pairs both right (verdict and flags) | 5 of 8 | reported |
| the run: cost (assessments · judge) · seconds per case (mean) · rewrites · regenerations | $0.1298 · $0.1817 · 75.6 s · 32 · 0 | reported |

Wrong verdicts: A-001 (Proceed → Proceed with conditions); A-008 (Proceed → Proceed with conditions); A-009 (Do not build as described → Proceed with conditions); A-012 (Proceed with conditions → Do not build as described); A-017 (Proceed with conditions → Do not build as described); A-019 (Proceed → Proceed with conditions); A-020 (Do not build as described → Proceed with conditions)
Must-cite misses: A-007: GDPR Art. 22; A-010: AI Act Annex III
Wrong extras: A-001: Finding 2 [Required]: requires checking and updating the notice to describe the strip's purpose and legal basis (GDPR Art. 13(1)), although the organisation facts say the existing notice already covers browsing activity inside the account; this is an obligation marked Required that the facts say is already done (contextual blindness).; A-010: Finding 1: Blocker invoking GDPR Art. 22 for the threshold hold, although the analyst reviews every hold within two hours, so the decision is not solely automated (false escalation and statutory misapplication).
Failed pairs: A-007+A-019, A-008+A-009, A-012+A-016

### Key findings, per case

**A-001** (Proceed with conditions):
- KF1 matched: Finding 4 (Covered) states that the 20-item cap, 30-day deletion and customer-only visibility limit the data retained and the retention period, which is the same minimisation and storage-limitation point. It cites GDPR Art. 5 (too general for a paragraph-level finding) and GDPR Art. 25, which is a listed acceptable alternative, so the provision is met.
- KF2 matched: Finding 3 (Covered) says the notice already covers browsing activity kept inside the account, citing GDPR Art. 13(1), which matches the expected point and provision at article level. Finding 2 separately marks a notice update as Required, which conflicts with the already-informed conclusion but does not change the match.
- wrong extras: Finding 2 [Required]: requires checking and updating the notice to describe the strip's purpose and legal basis (GDPR Art. 13(1)), although the organisation facts say the existing notice already covers browsing activity inside the account; this is an obligation marked Required that the facts say is already done (contextual blindness).

**A-002** (Proceed with conditions):
- KF1 matched: Finding 4 states the Chapter V route is needed before any transfer, 'typically appropriate safeguards if no applicable adequacy decision', citing GDPR Art. 46(1), with the same Required severity.
- KF2 matched: Finding 5 requires completing the processor contract before processing, covering instructions, confidentiality, subprocessors, assistance and return or deletion terms, citing GDPR Art. 28(1) and 28(3) at Required.
- KF3 matched: Finding 6 says to update privacy information to 'identify the vendor/recipient category and disclose the India transfer and applicable transfer safeguards', citing GDPR Art. 13(1) at Required.

**A-003** (Do not build as described):
- KF1 matched: Finding 1 (Blocker, GDPR Art. 22, Rec. 71) states that fully automated rejections need human decision-making, human intervention and a right to contest, and that a valid exception is needed. This matches the gist and the Blocker severity.
- KF2 matched: Finding 5 (Required, GDPR Art. 35(3)) says a DPIA is required because of systematic automated evaluation for significant-effect decisions. Art. 35(3) satisfies the article-level citation and the severity is Required.
- KF3 matched: Finding 6 (Required, AI Act Annex III point 5) classifies creditworthiness scoring as high-risk. Finding 7 (Required, AI Act Art. 26(2), 26(11)) covers human oversight and informing applicants, and Art. 26 is an acceptable alternative.
- KF4 matched: Finding 6 (Required) says to complete the deployer fundamental-rights impact assessment before first use, citing AI Act Art. 27(1) and 27(3). This matches the gist and the provision with the right severity.
- KF5 matched: Finding 4 (Required, GDPR Art. 6(1)) says browsing behaviour must have its necessity and lawful basis justified separately. It covers the paragraph-level Art. 6(1) and the Required severity, though it does not explicitly say the data is unnecessary under the contract basis.
- KF6 matched: Finding 9 (Covered, GDPR Art. 45(1)) states the US vendor transfer is covered by the organisation's stated EU-US Data Privacy Framework certification. This matches the gist, provision and Covered severity.

**A-004** (Proceed with conditions):
- KF1 matched: Finding 7 is Covered and cites GDPR Art. 22 and Rec. 71, stating that the analyst decision avoids solely automated decision-making only if the review is meaningful and independent and customers can contest; finding 5 adds authority to override.
- KF2 matched: Finding 3 is Required, cites GDPR Art. 35(1) and 35(3), and requires a DPIA before processing for high-risk profiling with significant effects, which satisfies the article-level citation.
- KF3 matched: The summary states the scoring is high-risk AI even though an analyst decides, and finding 4 is Required and places creditworthiness scoring within Annex III point 5(b); Art. 6(2) is absent, but the classification point is present at the Annex III paragraph level with the right severity.
- KF4 matched: Finding 4 is Required and cites AI Act Art. 27(1) for a fundamental-rights impact assessment before first deployment, explicitly tied to Annex III point 5(b) creditworthiness scoring.
- KF5 partial: Finding 6 is Required and covers informing customers about scoring logic and consequences under GDPR Art. 13(2), an acceptable alternative, but it never says that a high-risk AI system is evaluating them, so the AI Act Art. 26(11) point is not made.

**A-005** (Proceed with conditions):
- KF1 matched: Finding 4 requires telling customers 'clearly, no later than their first interaction, that the chatbot is an AI system' with AI Act Art. 50(1), at Required severity, which matches the expected notice point and provision.
- KF2 partial: Finding 6 (Covered) only argues that GDPR Art. 22 automated-decision rules are not triggered; the not-high-risk conclusion appears only in the header and summary, with no Annex III or Art. 6(3) reference, so the provision is missing.
- KF3 matched: Finding 3 (Required) requires the notice to include the retention period under GDPR Art. 13(1)/(2), and finding 5 (Required) sets and implements a retention period and minimises data; together they cover the transcript-retention point, though finding 5 cites bare 'GDPR Art. 5' rather than Art. 5(1)(e).

**A-006** (Do not build as described):
- KF1 matched: Finding 1 (Blocker) says final automated refusals need a valid Art. 22 basis and "an effective way to obtain human intervention and contest the decision", citing GDPR Art. 22 and Rec. 71; this is the same point, the provision is right and the severity is Blocker.
- KF2 matched: Finding 4 (Required) says to carry out a DPIA before launch because the feature "systematically evaluates individuals through automated decisions", citing GDPR Art. 35(3); the return-history profiling is covered by finding 3 but the DPIA point is in finding 4, with the right article and Required severity.
- KF3 matched: Finding 5 (Required) says customers must be told they are interacting with AI at first interaction, citing AI Act Art. 50(1); same point, right provision, Required severity.
- KF4 partial: The summary says "The refund-decision use is not within the AI Act high-risk categories identified here", which makes the same point but cites no Annex III provision and is not presented as a labelled finding; the Covered conclusion is implicit only, and no finding in the list states it.

**A-007** (Proceed with conditions):
- KF1 missed: No assistant finding says Art. 22 does not apply. The summary states that 'GDPR Article 22 ... do not appear to apply', but that sentence is not one of the numbered findings, so the point is absent from the findings.
- KF2 matched: Finding 1 (Required) says 'Document a lawful basis and balancing assessment for this use of transaction data' and cites GDPR Art. 6(1) and Rec. 47. The paragraph level is met and the Required severity matches; the point (f) is not named but the balancing test is present.
- KF3 matched: Finding 5 (Covered) says 'Personalised offers can be turned off in settings... Verify ... that opting out stops the profiling', citing GDPR Art. 21, which matches the settings switch as the objection mechanism at Covered severity. Finding 2 (Required) also covers the settings objection but at the wrong severity and is not needed for the match.
- KF4 missed: The assessment states 'DPIA required False' and 'DPIA is not mandatory on the facts provided'. Its only DPIA reference is 'reassess DPIA need if these facts indicate likely high risk' in the next steps, so the Required DPIA point under Art. 35(1) is absent.

**A-008** (Proceed with conditions):
- KF1 matched: Finding 6 (Covered) says the signed DPA, written-instruction limitation and end-of-contract deletion address key processor-contract requirements, citing 'GDPR Art. 28(3)'. That is the same Art. 28 relationship point, with the expected provision and the right severity.
- KF2 matched: Finding 7 (Covered) says the notice's 'analytics providers' recipient category covers the described recipients, citing 'GDPR Art. 13(1)'. That is the same recipient-category point at article level under Art. 13, with Covered severity.

**A-009** (Proceed with conditions):
- KF1 missed (severity miscalibrated): Finding 2 makes the compatibility and lawful-basis point under GDPR Art. 6(4) and Art. 6(1), saying the reuse is a distinct purpose needing a documented basis and may need prohibiting. The provision and point match, but the severity is 'Required' where the expected finding is 'Blocker' (stop and redesign), so the verdict is missed with severity miscalibrated.
- KF2 matched: Finding 3 states that where Northline determines purposes and means it is a controller for that processing, cites GDPR Art. 28(10), and says a processor arrangement cannot authorise independent use. The point, provision and Required severity all match.
- KF3 matched: Finding 4 requires updating customer information to cover the model-training purpose and recipient/controller information under GDPR Art. 13(1) and Art. 14(1), which are within the acceptable alternatives (Art. 13 and Art. 14), at Required severity. The condition 'if the reuse proceeds lawfully' does not change the substance.
- KF4 missed: No numbered finding addresses a DPIA under Art. 35(1). The only mention is a next step to 'complete a DPIA screening based on scale and risks', the verdict states 'DPIA required False', and Art. 35 is never cited, so the required DPIA obligation is absent.

**A-010** (Proceed with conditions):
- KF1 partial: Summary states the fraud use is 'not high-risk under the AI Act creditworthiness category, which excludes systems used to detect financial fraud', so the point is present with the right conclusion, but no Annex III point 5 citation is given, only the umbrella category, so the provision is incomplete.
- KF2 missed (severity miscalibrated): Finding 1 treats the threshold hold as an automated measure and makes it a Blocker under 'GDPR Art. 22'; it never recognises that the two-hour analyst review makes the decision not solely automated, so the point is reversed and the severity is Blocker rather than Covered.
- KF3 matched: Finding 2 says 'Complete a DPIA before deployment: the system evaluates transactions systematically at scale', Required, citing GDPR Art. 35(3), which matches the systematic evaluation point and the expected severity.
- KF4 matched: Finding 8 says the US vendor 'is certified under the EU-US Data Privacy Framework; the transfer is covered by the adequacy decision', Covered, citing GDPR Art. 45(1), matching the expected point, provision and severity.
- KF5 matched: Finding 6 requires the vendor to 'act only on documented instructions' with 'security, assistance, deletion or return, and controls on subprocessors', Required, citing GDPR Art. 28(3), which matches the processor contract point.
- wrong extras: Finding 1: Blocker invoking GDPR Art. 22 for the threshold hold, although the analyst reviews every hold within two hours, so the decision is not solely automated (false escalation and statutory misapplication).

**A-011** (Proceed with conditions):
- KF1 matched: Finding 1 says 'The fine-tuned system evaluates creditworthiness and is high-risk' citing AI Act Annex III point 5 at Required, which matches the classification gist and provision.
- KF2 matched: Finding 1 says 'Putting it under your brand and modifying the vendor model likely makes your organisation its provider' with 'AI Act Art. 25(1)' and Required, covering the provider-shift point and its citation.
- KF3 matched: Finding 2 requires documenting the lawful basis and 'whether this further use is compatible' under GDPR Art. 6(4), plus 'Limit the training data' at Required. The minimisation point is cited only to bare 'GDPR Art. 5', but the key Art. 6(4) provision is present.
- KF4 matched: Finding 3 says 'complete the AI Act fundamental-rights impact assessment before first use as a creditworthiness system' citing AI Act Art. 27(1) at Required.
- KF5 matched: Finding 3 says 'Complete a GDPR DPIA before processing: this is systematic evaluation informing consequential credit-limit decisions' citing GDPR Art. 35(3) at Required, which satisfies the article-level citation.
- KF6 missed: Finding 4 covers GDPR transparency about processing, profiling and logic under Art. 13(2)/14(2), but never states that a high-risk AI system is used on the customers and cites no AI Act Art. 26(11) duty to inform before use. The point is absent.
- KF7 matched: Finding 5 says the 'credit officer's approval or change and the customer review route are safeguards against a solely automated final decision', citing GDPR Art. 22 at Covered, with the officer needing authority to override.

**A-012** (Do not build as described):
- KF1 matched: Finding 7 states the one-to-one use is excluded from the AI Act Annex III point 1(a) category as "Covered", which matches the expected point, provision and severity.
- KF2 missed (severity miscalibrated): Finding 1 makes the same point (biometric processing for unique identification needs explicit, freely given consent, with the video-call route equivalent) and cites GDPR Art. 9(2), but labels it "Blocker" where Required is expected, so the severity is wrong.
- KF3 matched: Finding 4 is "Required" and requires a DPIA before launch citing GDPR Art. 35(1), which is an acceptable alternative provision for this expected finding.
- KF4 partial: Finding 6 is "Covered" and makes the storage-limitation point that immediate deletion of face templates limits storage, but it cites only "GDPR Art. 5" without the paragraphs 5(1)(c) or 5(1)(e) that this paragraph-level finding requires.

**A-013** (Do not build as described):
- KF1 matched: Finding 1 is a Blocker that states the solely automated rejection needs meaningful human review and a way to contest, citing GDPR Art. 22, which covers Art. 22(1) at article level. This matches the expected point, provision and severity.
- KF2 matched: Finding 2 is Required and treats recruitment and selection AI as high-risk under AI Act Annex III point 4, requiring human oversight by trained, competent staff. The expected Annex III point 4 is cited at the point level the reviewer asked for, so it matches.
- KF3 matched: Finding 3 is Required and requires a DPIA before processing because candidates are systematically evaluated with decisions that significantly affect them, citing GDPR Art. 35(3). This matches the expected point, provision and severity.
- KF4 matched: Finding 4 is Required and requires telling applicants about the screening and meaningful information on the automated decision logic and consequences, noting the current design does not disclose the tool, citing GDPR Art. 13(2). Art. 13 is an acceptable article-level provision, so it matches.

**A-014** (Proceed with conditions):
- KF1 matched: Finding 1 identifies recruitment ranking as a high-risk use under "AI Act Annex III point 4" and sets out the deployer duties (recruiter training, monitoring, overriding rankings, Art. 26(1) and 26(2)) at Required severity, matching the expected point and paragraph-level provision.
- KF2 matched: Finding 8 is Covered and cites "GDPR Art. 22, GDPR Rec. 71", stating that "a recruiter reads every application... applicants can request human-only review" and that the recruiter must "independently assess applications and can disregard the score rather than rubber-stamp it", which is the meaningful-review point.
- KF3 matched: Finding 2 is Required, "Carry out a DPIA before processing", citing GDPR Art. 35(1), an acceptable alternative; it covers the assessment of candidate impacts and the ranking's role in invitation decisions, though it does not use the phrase systematic evaluation.
- KF4 missed (severity miscalibrated): The informing-applicants point with GDPR Art. 13 is present in finding 5, but it is labelled "[Required]" where Covered is expected, so the severity is wrong and the verdict is missed.

**A-015** (Proceed with conditions):
- KF1 matched: Finding 1 (Required) names the employment high-risk category under AI Act Annex III point 4 and Art. 6(2), covering performance-based allocation and evaluation, with competent human oversight. This matches the expected point, provision level and Required severity.
- KF2 matched: Finding 8 (Required) requires informing affected workers and workers' representatives before workplace use under AI Act Art. 26(7), and says a handbook entry should not be assumed to suffice. This matches the expected gist, provision and severity.
- KF3 matched: Finding 2 (Required) requires a DPIA before processing for systematic automated evaluation of staff with effects on schedules and reviews, citing GDPR Art. 35(1) and 35(3). Art. 35(1) and 35(3) are both acceptable alternatives, and the severity is Required.
- KF4 partial: Finding 3 (Required) asks for a documented legal basis for performance data use, but cites only GDPR Art. 6(1). It never says employee consent is not free, never names legitimate-interest balancing, and omits Art. 88 and the national employment rules, which appear only in the next steps. The point is partly there at the right severity but the reasoning and provisions are incomplete.
- KF5 matched: Finding 9 (Covered) states that team leads make the flag decisions, so Art. 22 is not triggered on the current facts, and that review must be substantive with authority to override. This matches the gist, provision and Covered severity.

**A-016** (Do not build as described):
- KF1 matched: Finding 1 (Blocker) says face matching for unique identification processes biometric data under GDPR Art. 9(1) and that no Art. 9(2) condition is given, so the design should not be built; this is the same point at the expected paragraph level with the right severity.
- KF2 missed (severity miscalibrated): Finding 3 cites AI Act Annex III point 1 and says remote biometric identification is high-risk only where law permits, but it is labelled Blocker where the expected severity is Required, so the point and provision are right and only the severity is wrong. Art. 6(2) and the deployer registration and oversight duties are not mentioned.
- KF3 matched: Finding 2 (Blocker, GDPR Art. 10) says the watch-list of fraud suspects may be processed only under official authority or Union or Member State law authorisation, and that the description identifies neither, so offence data must not be used without it.
- KF4 matched: Finding 4 (Required, GDPR Art. 35(3)) requires a DPIA before processing because of systematic biometric identification that may meet the large-scale special-category or publicly-accessible-area monitoring criteria; the article-level citation and the Required severity match the expected finding.

**A-017** (Do not build as described):
- KF1 missed (severity miscalibrated): Finding 1 makes the Art. 9(2) condition point, citing GDPR Art. 9(1) and 9(2), but it is a Blocker and never names explicit consent or a route that avoids medical proof. The severity is wrong (Required expected) and the specific Art. 9(2)(a) gist is absent.
- KF2 partial: Finding 4 covers minimum proof, retention and erasure when no longer necessary, and finding 3 covers necessary recording of categories, both Required, but they cite only a bare 'GDPR Art. 5' rather than 5(1)(c) and 5(1)(e). The point and severity are right but the provision is at the wrong level.
- KF3 matched: Finding 5 requires a DPIA before processing covering the sensitivity of the evidence and the vulnerable customers, rated Required and citing GDPR Art. 35(1), which is an acceptable alternative.
- KF4 missed: No assistant finding states that a human case handler decides the payment holiday so Art. 22 does not apply. Art. 22 is never mentioned.

**A-018** (Do not build as described):
- KF1 matched: Finding 1 states the inferred religion is special-category data, prohibited as described, with no Art. 9(2) condition identified; it gives Blocker and cites GDPR Art. 9(1), matching the expected point, provision and severity.
- KF2 matched: Finding 5 requires a clear way to object and stop using the profile for marketing, cited as GDPR Art. 21 (an acceptable alternative) at Required, which matches the expected right to object free of charge.
- KF3 matched: Finding 4 requires a DPIA before processing for sensitive profiling at Required, citing GDPR Art. 35(1) and Rec. 75; Art. 35 is an acceptable alternative to the expected Art. 35(3)(b).
- KF4 partial: The only trace is the header verdict field 'high-risk AI False'; no finding discusses Annex III or explains why marketing segmentation is not a high-risk use, so the point is present but without any provision, and the Covered label is not stated.

**A-019** (Proceed with conditions):
- KF1 matched: Finding 5 (Covered) states that the customer-only display is not a decision and that Article 22's restriction is not triggered, citing GDPR Art. 22 and Rec. 71. This is the same point at the same severity with the expected provision.
- KF2 missed (severity miscalibrated): Finding 1 identifies the Article 6 lawful-basis point but gives it Required rather than Covered, and cites Art. 6(1) generally rather than the contract ground in 6(1)(b). No other finding covers contract performance as the basis, so the point is missed on severity.
- KF3 matched: Finding 4 (Covered) says the computation is on demand, categories are not persisted, and processing is confined to the customer's own data, citing GDPR Art. 5 and Art. 25. Art. 25 is an acceptable alternative, so the provision is met and the severity is right.

**A-020** (Proceed with conditions):
- KF1 partial: Finding 1 is Blocker and cites GDPR Art. 17(3)(b) for credit-scoring audit logs that must not be wiped, which matches the logs half of the point. The AML transaction-records half sits in finding 2, which is Required rather than Blocker, so the severity for that half is wrong.
- KF2 matched: Finding 1 is Blocker and cites AI Act Art. 26(6) for keeping high-risk AI logs for at least six months, so the point, provision and severity all match.
- KF3 matched: Finding 3 is Required and says to map the identifiers needed for retained records, "restrict them to that purpose", and erase the rest, citing GDPR Art. 5, which is the article of the listed alternative Art. 5(1)(e).
- KF4 partial: Finding 4 is Required and cites Art. 12(3) for telling the requester "what action was taken", but it does not say which data is kept and under which obligation; the summary's "explaining any refusal or partial refusal" only partly covers the why.


## Judge versus human

The judge agreed with the human reader on 13 of 15 findings (4 marked unsure and left out); target ≥ 17 of 20. Disagreements: A-003 KF1: human partial, judge matched; A-003 KF5: human partial, judge matched. In 2 of the disagreements the judge was the more generous.
