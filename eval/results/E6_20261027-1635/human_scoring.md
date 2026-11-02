# Human scoring sheet (E6)

Score each expected key finding against the assistant's findings with the rubric of eval/prompts/judge_findings.md,
WITHOUT looking at the judge's verdicts (they are in cases.jsonl). Fill the word after `verdict:` on each line with
matched, partial, missed or unsure; then run `python -m eval.run_eval agreement <this folder>`.

## A-001 · Recently viewed products strip

Feature: We want to add a 'recently viewed products' strip on the homepage. The list lives in the customer's own account, holds the last twenty items, is deleted after thirty days, is shown only to that customer and is not used for anything else. Our privacy notice already says we keep browsing activity inside the account.

Assistant's verdict: Proceed with conditions · risk low · high-risk AI False · DPIA False

Assistant's findings:
1. [Required] Document a lawful basis for recording and displaying viewed products. Legitimate interests may be plausible in this customer-account context, but assess and document the balance before launch. (GDPR Art. 6(1), GDPR Rec. 47)
2. [Required] Check that the notice specifically explains the recently viewed-products display and states the processing purpose and legal basis; update it if it does not. (GDPR Art. 13(1))
3. [Covered] The notice already says browsing activity is kept inside the account, providing information about the activity and its account context. (GDPR Art. 13(1))
4. [Covered] The stated cap of 20 items, 30-day deletion, and customer-only visibility limit the data retained, retention period, and access in line with the described purpose. (GDPR Art. 5, GDPR Art. 25)

Expected key findings:
- KF1: twenty items, thirty days, one purpose: the principles are satisfied, nothing more is kept than the feature needs · provisions GDPR Art. 5(1)(c), GDPR Art. 5(1)(e) (alternatives: GDPR Art. 25) · severity Covered · citation level paragraph
- KF2: the existing privacy notice covers browsing activity inside the account · provisions GDPR Art. 13 (alternatives: none) · severity Covered · citation level article

- [A-001 KF1] verdict: matched
- [A-001 KF2] verdict: matched

## A-002 · Customer support ticket hosting by helpdesk vendor in India

Feature: We're moving all customer support ticket data (names, order numbers, the text of the complaints) to a new helpdesk vendor whose servers are in India. The vendor will host and process the tickets for us. The contract is still being negotiated.

Assistant's verdict: Proceed with conditions · risk high · high-risk AI False · DPIA False

Assistant's findings:
1. [Blocker] Complaint text may reveal special-category data (for example, health or political information). Do not process such content unless an Article 9(2) condition applies; otherwise prevent or remove it from vendor-hosted tickets. DPO review is required before build if this data is involved. (GDPR Art. 9(1), GDPR Art. 9(2))
2. [Required] For names, document the customer-support purpose and an Article 6 legal basis; limit access and retention to what that purpose needs. (GDPR Art. 6(1), GDPR Art. 5, GDPR Art. 32)
3. [Required] For order numbers, confirm they are necessary for resolving tickets and set a retention period tied to that purpose; do not retain them longer than necessary. (GDPR Art. 5, GDPR Art. 25)
4. [Required] India is a third country. Before any transfer, establish and document an available Chapter V route—typically appropriate safeguards if no applicable adequacy decision—and confirm enforceable rights and effective remedies; do not rely on the contract alone as proof of transfer compliance. (GDPR Art. 45(1), GDPR Art. 46(1))
5. [Required] Complete the processor contract before processing, including instructions, confidentiality, security, subprocessors, assistance, audit rights, and return or deletion terms; verify the vendor provides sufficient guarantees. (GDPR Art. 28(1), GDPR Art. 28(3))
6. [Required] Update the relevant privacy information to identify the vendor/recipient category and disclose the India transfer and applicable transfer safeguards. (GDPR Art. 13(1), GDPR Art. 14(1))
7. [Required] Record the India transfer, recipient, erasure periods where known, and security measures in the processing record; record the transfer in the transfer log as well. (GDPR Art. 30(1))
8. [Required] Assess the vendor’s security measures, including access controls, encryption, resilience, and security testing, in light of ticket data and transfer risks. (GDPR Art. 32)

Expected key findings:
- KF1: standard contractual clauses or another Art. 46 instrument before any data moves; India has no adequacy decision · provisions GDPR Art. 46 (alternatives: GDPR Art. 44) · severity Required · citation level article
- KF2: instructions, confidentiality, sub-processors, assistance, deletion at the end · provisions GDPR Art. 28 (alternatives: none) · severity Required · citation level article
- KF3: the privacy notice names the recipient category and the transfer with its safeguard · provisions GDPR Art. 13 (alternatives: GDPR Art. 13(1)(f)) · severity Required · citation level article

- [A-002 KF1] verdict: unsure
- [A-002 KF2] verdict: matched
- [A-002 KF3] verdict: matched

## A-003 · Automated BNPL credit scoring and US fraud-vendor sharing

Feature: We're adding automated credit scoring to our buy-now-pay-later checkout using transaction history, device fingerprint and browsing behaviour. Rejections are fully automatic and scores are shared with our US fraud-prevention vendor.

Assistant's verdict: Do not build as described · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Blocker] Do not launch fully automated rejections as described. Such decisions fall under Art. 22; redesign for meaningful human decision-making or establish a valid exception (contract necessity, law, or explicit consent) and, where applicable, safeguards including human intervention, the right to express a view and contest the decision. (GDPR Art. 22, GDPR Rec. 71)
2. [Required] Transaction history: document the lawful basis and demonstrate that the history used is necessary and proportionate for this scoring purpose; limit fields and retention accordingly. (GDPR Art. 6(1), GDPR Art. 5)
3. [Required] Device fingerprint: treat device-linked identifiers as potentially personal data; document necessity and lawful basis, and minimise collection and retention. (GDPR Rec. 30, GDPR Art. 6(1), GDPR Art. 5)
4. [Required] Browsing behaviour: it can constitute profiling. Justify its necessity and lawful basis separately, and explain the profiling, data source, logic and consequences to applicants. (GDPR Art. 4(4), GDPR Art. 6(1), GDPR Art. 14(2))
5. [Required] Complete a DPIA before processing: systematic automated evaluation used for decisions with significant effects requires one. (GDPR Art. 35(3))
6. [Required] The creditworthiness scoring system is high-risk AI. Before first use, complete the deployer fundamental-rights impact assessment and notify the market surveillance authority of its results. (AI Act Annex III point 5, AI Act Art. 27(1), AI Act Art. 27(3))
7. [Required] Assign competent, trained and authorised human oversight, and inform applicants that they are subject to the high-risk AI system when it makes or assists decisions about them. (AI Act Art. 26(2), AI Act Art. 26(11))
8. [Required] Provide applicants with information on the processing, including the existence of automated decision-making, meaningful information about its logic, significance and consequences, and applicable data sources and rights. (GDPR Art. 13(2), GDPR Art. 14(2))
9. [Covered] The US fraud-prevention vendor’s transfer is covered by the organisation’s stated EU-US Data Privacy Framework certification fact; record each transfer in the transfer log. (GDPR Art. 45(1))

Expected key findings:
- KF1: fully automatic rejections with no human intervention and no way to contest; the Art. 22(2)(a) contract exception would still need the 22(3) safeguards · provisions GDPR Art. 22(1), GDPR Art. 22(3) (alternatives: GDPR Rec. 71, GDPR Art. 22(2)) · severity Blocker · citation level article
- KF2: systematic and extensive evaluation based on profiling · provisions GDPR Art. 35(3)(a) (alternatives: GDPR Art. 35) · severity Required · citation level article
- KF3: deployer obligations apply: human oversight, information to the persons concerned · provisions AI Act Annex III point 5, AI Act Art. 6(2) (alternatives: AI Act Art. 26) · severity Required · citation level paragraph
- KF4: a deployer of an Annex III 5(b) credit-scoring system owes a FRIA alongside the DPIA · provisions AI Act Art. 27 (alternatives: none) · severity Required · citation level article
- KF5: browsing data is not necessary for a credit decision under the contract basis; drop it or justify it · provisions GDPR Art. 5(1)(c), GDPR Art. 6(1) (alternatives: GDPR Art. 6(4), GDPR Art. 5) · severity Required · citation level paragraph
- KF6: covered by the vendor's DPF certification, an organisation fact · provisions GDPR Art. 45 (alternatives: none) · severity Covered · citation level article

- [A-003 KF1] verdict: partial
- [A-003 KF2] verdict: matched
- [A-003 KF3] verdict: matched
- [A-003 KF4] verdict: matched
- [A-003 KF5] verdict: partial
- [A-003 KF6] verdict: matched

## A-004 · BNPL checkout credit scoring using transaction history and device data

Feature: We're adding credit scoring to our buy-now-pay-later checkout using transaction history and device data. The score only flags an order; a credit analyst reviews every flagged order and takes the decision, and the customer is told how to appeal. Scores stay in-house.

Assistant's verdict: Proceed with conditions · risk high · high-risk AI True · DPIA True

Assistant's findings:
1. [Required] Transaction-history data: document a lawful basis for this scoring purpose and ensure the history used is necessary, accurate, and retained no longer than necessary; confirm the original collection purposes allow this use. (GDPR Art. 6(1), GDPR Art. 6(4), GDPR Art. 5)
2. [Required] Device data: document a lawful basis and justify each device signal as necessary and relevant; limit collection and retention, and test for inaccurate or unfair proxy effects. (GDPR Art. 6(1), GDPR Art. 5)
3. [Required] Complete a DPIA before processing, given the high-risk profiling and potential significant effects of credit scoring; record risks and mitigations. (GDPR Art. 35(1), GDPR Art. 35(3))
4. [Required] Perform the AI Act fundamental-rights impact assessment before first deployment: creditworthiness scoring falls within Annex III point 5(b). (AI Act Art. 27(1), AI Act Annex III point 5)
5. [Required] Ensure analysts have competence, training, and authority to disregard or override the score, and monitor system performance and input-data representativeness. (AI Act Art. 26(2), AI Act Art. 26(4), AI Act Art. 26(5), AI Act Art. 14(4))
6. [Required] Give customers timely information about the scoring purpose, lawful basis, retention, and meaningful information about the logic and likely consequences; include profiling information where relevant. (GDPR Art. 13(1), GDPR Art. 13(2))
7. [Covered] A human analyst decides each flagged order and customers are told how to appeal; this avoids a solely automated decision only if the analyst conducts meaningful, independent review and customers can contest the decision. (GDPR Art. 22, GDPR Rec. 71)

Expected key findings:
- KF1: an analyst takes every decision and the customer can appeal, so Art. 22(1) does not bite; the review must be meaningful, with the authority and competence to overturn the score (not a rubber stamp) · provisions GDPR Art. 22 (alternatives: GDPR Rec. 71, AI Act Art. 14) · severity Covered · citation level article
- KF2: systematic evaluation based on profiling · provisions GDPR Art. 35(3)(a) (alternatives: GDPR Art. 35) · severity Required · citation level article
- KF3: human oversight does not remove the classification; deployer obligations apply, including competent oversight · provisions AI Act Annex III point 5, AI Act Art. 6(2) (alternatives: AI Act Art. 26, AI Act Art. 14) · severity Required · citation level paragraph
- KF4: a deployer of an Annex III 5(b) credit-scoring system owes a FRIA alongside the DPIA · provisions AI Act Art. 27 (alternatives: none) · severity Required · citation level article
- KF5: being told the outcome and how to appeal is not being told that a high-risk AI system evaluated them; the deployer informs them before use · provisions AI Act Art. 26(11) (alternatives: AI Act Art. 26, GDPR Art. 13(2)(f)) · severity Required · citation level article

- [A-004 KF1] verdict: matched
- [A-004 KF2] verdict: unsure
- [A-004 KF3] verdict: matched
- [A-004 KF4] verdict: matched
- [A-004 KF5] verdict: unsure

## A-005 · Help-page chatbot for order status and returns

Feature: A chatbot on our help page answers order-status and returns questions from our FAQ. It reads the order number the customer types, shows the status, and hands over to a human agent whenever the customer asks or the question is not in the FAQ. It takes no decisions about customers.

Assistant's verdict: Proceed with conditions · risk low · high-risk AI False · DPIA False

Assistant's findings:
1. [Required] Document a lawful basis for using the typed order number to identify the order and retrieve its status; limit this use to the support purpose. (GDPR Art. 6(1), GDPR Art. 5)
2. [Required] Treat the retrieved order status as personal data when linked to the customer. Restrict retrieval to the relevant customer's order and avoid exposing other order details. (GDPR Art. 5, GDPR Art. 25)
3. [Required] Provide the customer with the processing purposes, lawful basis, recipients, retention period and applicable rights information when collecting the order number. (GDPR Art. 13(1), GDPR Art. 13(2))
4. [Required] Tell customers clearly, no later than their first interaction, that the chatbot is an AI system. (AI Act Art. 50(1), AI Act Art. 50(5))
5. [Required] Set and implement a retention period for order numbers and chatbot interactions that is no longer than needed for support; collect and retain only what the chatbot needs. (GDPR Art. 5, GDPR Art. 25)
6. [Covered] The chatbot only retrieves order status and provides FAQ answers; it makes no customer decisions and hands off to a human on request or when it cannot answer. On the described design, GDPR automated-decision restrictions are not triggered. (GDPR Art. 22)

Expected key findings:
- KF1: a clear notice at the start of the chat; the hand-over to a human is already there · provisions AI Act Art. 50(1) (alternatives: AI Act Art. 50) · severity Required · citation level article
- KF2: FAQ answers and order status are none of the Annex III uses and it takes no decisions · provisions AI Act Annex III (alternatives: AI Act Art. 6(3), AI Act Art. 6) · severity Covered · citation level article
- KF3: say how long transcripts are kept and that they are processed; keep them short · provisions GDPR Art. 5(1)(e), GDPR Art. 13 (alternatives: GDPR Art. 5) · severity Required · citation level paragraph

- [A-005 KF1] verdict: unsure
- [A-005 KF2] verdict: partial
- [A-005 KF3] verdict: matched
