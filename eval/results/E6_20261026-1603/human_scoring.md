# Human scoring sheet (E6)

Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,
WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with
matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.

## A-003 · Automated BNPL credit scoring and rejection

Feature: We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US fraud-prevention vendor.

Assistant's verdict: Do not build as described · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Blocker] Exclude browsing behaviour from credit scoring and rejection entirely. The proposed use is prohibited by the organisation’s standing limit; data collected for another purpose cannot simply be reused for scoring. (GDPR Art. 5, GDPR Art. 6(4))
2. [Blocker] Do not launch fully automatic rejections until you establish an applicable Article 22 exception and provide the required safeguards, including human intervention and a way to contest the decision. Automatic credit rejection is the kind of significant decision covered here. (GDPR Art. 22, GDPR Rec. 71)
3. [Required] For transaction history, document its necessity, lawful basis, purpose compatibility if reused, and data minimisation. Do not assume prior collection for transactions authorises credit scoring. (GDPR Art. 5, GDPR Art. 6(1), GDPR Art. 6(4))
4. [Required] For device fingerprinting, justify its relevance and necessity for creditworthiness, identify a lawful basis, and minimise the data collected. Do not use it until that case is documented. (GDPR Art. 5, GDPR Art. 6(1))
5. [Required] This is high-risk AI for evaluating creditworthiness. Complete the required fundamental-rights impact assessment before first use, and implement the applicable high-risk system controls and human oversight. (AI Act Annex III point 5, AI Act Art. 27(1), AI Act Art. 26(2))
6. [Required] Complete a GDPR DPIA before processing; the system systematically evaluates people through automated processing and determines credit access. (GDPR Art. 35(1), GDPR Art. 35(3))
7. [Required] Tell applicants that high-risk AI is used and provide the required meaningful information about automated decisions, their logic and likely consequences. Establish a process for explanations where the AI Act right applies. (AI Act Art. 26(11), AI Act Art. 86, GDPR Art. 13(2))
8. [Required] Scores sent to the US fraud-prevention vendor are covered by the organisation’s Data Privacy Framework certification fact for this vendor; record each transfer in the transfer log. Confirm whether the vendor acts as processor and, if so, put the required processing terms in place. (GDPR Art. 45(1), GDPR Art. 28(1), GDPR Art. 28(3))

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
