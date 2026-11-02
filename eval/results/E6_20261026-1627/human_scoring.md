# Human scoring sheet (E6)

Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,
WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with
matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.

## A-003 · Automated BNPL credit scoring and rejection

Feature: We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US fraud-prevention vendor.

Assistant's verdict: Do not build as described · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Blocker] Fully automated credit refusals are likely decisions with legal or similarly significant effects. Establish and document an applicable Art. 22(2) exception; otherwise remove fully automated rejection. Where an exception applies, provide human intervention, the ability to state a position and contest the decision. (GDPR Art. 22, GDPR Rec. 71)
2. [Blocker] Device fingerprint: justify its necessity and proportionality for credit scoring and limit collection/use to what is necessary. Do not include it until that purpose-specific assessment and lawful basis are documented. (GDPR Art. 5, GDPR Art. 6(1))
3. [Blocker] Browsing behaviour: justify its necessity and proportionality for credit scoring and limit collection/use to what is necessary. Do not include it until that purpose-specific assessment and lawful basis are documented. (GDPR Art. 5, GDPR Art. 6(1))
4. [Required] Creditworthiness/credit-score AI is high-risk; the financial-fraud exception does not cover a system used for credit scoring. Complete a fundamental-rights impact assessment before deployment and meet the applicable high-risk deployer obligations. (AI Act Annex III point 5, AI Act Art. 27(1), AI Act Art. 26(2))
5. [Required] Transaction history: document why each history field and time window is necessary for credit scoring, ensure accuracy and set retention limits; identify and document a lawful basis for this purpose. (GDPR Art. 5, GDPR Art. 6(1))
6. [Required] Tell applicants about the scoring and automated decisions, including meaningful information about the logic, significance and expected consequences; provide applicable source, recipient and retention information. (GDPR Art. 13(2), GDPR Art. 14(2))
7. [Required] Scores sent to the vendor: document the disclosure’s purpose, scope, access controls and retention, and ensure the transfer remains within the vendor’s covered certification. Keep the transfer log entry. (GDPR Art. 5, GDPR Art. 45(1))
8. [Covered] The US vendor transfer is covered by its stated EU-US Data Privacy Framework certification, subject to confirming that the certification covers the vendor and relevant data; record each transfer in the transfer log. (GDPR Art. 45(1))

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
