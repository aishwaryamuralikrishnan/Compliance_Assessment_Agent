# Human scoring sheet (E6)

Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,
WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with
matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.

## A-003 · Automated BNPL credit scoring and rejection

Feature: We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US fraud-prevention vendor.

Assistant's verdict: Do not build as described · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Blocker] Exclude browsing behaviour from automated credit scoring and rejection. This use is prohibited for this feature; do not assume data collected for another purpose can be reused. (GDPR Art. 5, GDPR Art. 22)
2. [Blocker] Rejections are fully automated. Do not launch this design: automatic credit refusal is a significant decision, and any applicable GDPR exception would still require safeguards including human intervention and a way to contest the decision. (GDPR Art. 22, GDPR Rec. 71)
3. [Required] For transaction history, document the lawful basis, why these records are necessary for creditworthiness scoring, and controls for accuracy and retention. (GDPR Art. 6(1), GDPR Art. 5)
4. [Required] For device fingerprinting, justify its relevance and necessity for credit scoring, establish a lawful basis, and minimise the data collected and retained. Do not use it until these are demonstrated. (GDPR Art. 6(1), GDPR Art. 5)
5. [Required] This creditworthiness-scoring AI is high-risk. Meet applicable high-risk requirements, including assigning competent, trained and authorised human oversight; the current fully automatic rejection design also needs the GDPR redesign above. (AI Act Art. 6(2), AI Act Annex III point 5, AI Act Art. 26(2))
6. [Required] Complete a DPIA before processing. The planned systematic automated evaluation that determines checkout outcomes requires one. (GDPR Art. 35(1), GDPR Art. 35(3))
7. [Required] Tell customers about the automated scoring, its logic in meaningful terms, and its significance and likely consequences; also explain the data categories and purposes. (GDPR Art. 13(2))
8. [Covered] The US fraud-prevention vendor is certified under the EU-US Data Privacy Framework, so the transfer is covered by the adequacy decision. Record each transfer in the transfer log. (GDPR Art. 45(1))

Expected key findings:
- KF1: a person must be able to intervene and the customer must be able to contest · provisions GDPR Art. 22(1), GDPR Art. 22(3) (alternatives: GDPR Rec. 71) · severity Blocker · tolerance none
- KF2: systematic and extensive evaluation based on profiling · provisions GDPR Art. 35(3)(a) (alternatives: GDPR Art. 35) · severity Required · tolerance one-level
- KF3: provider or deployer obligations apply · provisions AI Act Annex III point 5, AI Act Art. 6(2) (alternatives: AI Act Art. 26) · severity Required · tolerance one-level
- KF4: browsing data is not needed for a credit decision; drop it or justify it · provisions GDPR Art. 5(1)(c), GDPR Art. 6 (alternatives: GDPR Art. 5) · severity Required · tolerance one-level
- KF5: covered by the vendor's DPF certification, an organisation fact · provisions GDPR Art. 45 (alternatives: none) · severity Covered · tolerance none

- [A-003 KF1] verdict: 
- [A-003 KF2] verdict: 
- [A-003 KF3] verdict: 
- [A-003 KF4] verdict: 
- [A-003 KF5] verdict: 
