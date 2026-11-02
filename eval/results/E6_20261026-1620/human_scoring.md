# Human scoring sheet (E6)

Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,
WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with
matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.

## A-003 · Automated BNPL credit scoring and US fraud-vendor sharing

Feature: We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US fraud-prevention vendor.

Assistant's verdict: Do not build as described · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Blocker] Do not issue automatic rejections as described. Establish and document a valid GDPR Art. 22(2) exception (including why automated scoring is necessary for the contract if relying on that ground) and provide meaningful human review, a way to contest, and an opportunity to state the applicant’s view before deployment. (GDPR Art. 22, GDPR Rec. 71)
2. [Blocker] This is high-risk AI for evaluating creditworthiness; the financial-fraud exception is not established for the credit-scoring purpose. Meet the applicable high-risk AI requirements, including competent human oversight with authority to disregard outputs. (AI Act Annex III point 5, AI Act Art. 26(2), AI Act Art. 14(4))
3. [Required] Transaction history: document a lawful basis and show these records are necessary and relevant for BNPL credit assessment; limit the history used and set a justified retention period. (GDPR Art. 6(1), GDPR Art. 5)
4. [Required] Device fingerprint: justify its necessity and use for credit scoring separately, minimise the fingerprint data, and specify its retention; do not assume fraud-prevention use automatically justifies creditworthiness assessment. (GDPR Art. 6(1), GDPR Art. 5)
5. [Required] Browsing behaviour: demonstrate a lawful basis, purpose compatibility, and necessity for credit scoring; otherwise exclude it. Explain this profiling and its consequences to applicants. (GDPR Art. 6(1), GDPR Art. 5, GDPR Art. 13(2))
6. [Required] Complete a DPIA before processing because decisions with legal or similarly significant effects are based on systematic, extensive automated evaluation. (GDPR Art. 35(3))
7. [Required] Tell applicants about the automated decision-making, meaningful information about its logic, significance and consequences, and the data used; include the applicable human-review and challenge route. (GDPR Art. 13(2), GDPR Art. 22, GDPR Rec. 71)
8. [Covered] The US vendor transfer is covered by the organisation’s Data Privacy Framework certification fact, subject to verifying that certification remains applicable to the vendor and transfer; log each transfer. (GDPR Art. 45(1))

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
