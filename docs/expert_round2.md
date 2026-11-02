# Compliance Assistant · expert review, round 2

The remaining fifteen end-to-end cases (round 1 had the first five). Same format as before: the feature as the
product manager would write it, then what we expect the assistant to say, and a line `Your view:` per case. Agree /
disagree and one line why is all that is needed; if you disagree, say which finding you would change, add or drop,
and why.

Words used: **Blocker** = the feature as described is unlawful and must change before it can be built;
**Required** = an obligation to fulfil before launch while the design stands (a contract, a notice, a DPIA);
**Covered** = already handled, by the design or by a fact about the organisation. "High-risk AI" and "DPIA" are
yes/no flags the assistant sets. The provisions in brackets are the ones we expect to be cited; the assistant may
cite others for the same point and we list the ones we would accept in the data file. Two lists close each case:
*merely extra* are correct points the assistant may add without penalty, *wrong* are points that count against it
if it makes them. Where a case has a pair, the two sound alike but have different answers; please check that the
difference we expect is the right one.

A reminder of the organisation: an EU fintech of about eighty staff with a named DPO; its US fraud-prevention
vendor is certified under the EU-US Data Privacy Framework (a fact the assistant has in memory).

> **Status (27 Oct).** Reviewed the same day by Gemini 3.1 (Argon 4) acting as the DPO, as a *preliminary* review,
> and applied: A-007's objection finding made Covered; Art. 26(11) (telling people a high-risk system is used on
> them) made its own Required finding in A-004 and A-011 and added to A-013; "sick days" removed from A-015's
> inputs; A-016's Art. 10 finding made a Blocker; A-011 reworked around fine-tuning the vendor's model under the
> organisation's own brand (AI Act Art. 25); A-020 replaced by the "Delete my account" case. Rows carry
> `reviewed_by: "gemini (preliminary, round 2)"` until the human expert has seen them; her answers replace
> Gemini's wherever the two differ. The cases below are the rows as they now stand.

### A-006 · A new AI component that is not high-risk · pair of A-005

> Same chatbot on our help page as before, but we also want it to handle refund claims: it reads the order, the customer's return history and our refund policy, and approves or refuses refunds up to 500 euros on its own. Refusals are final; there is no way for the customer to reach a person about a refused claim.

Expected: **Do not build as described**, medium risk, not high-risk AI, DPIA required.

1. **Blocker** — solely automated refusal with a significant effect and no human intervention (GDPR Art. 22(1), GDPR Art. 22(3)). A final refusal of up to 500 euros decided by the bot alone, with no way to obtain human intervention or contest it; refusing a refund claim denies a contractual right (a legal effect) and the loss is significant, so Art. 22 applies, and even under the contract exception the 22(3) safeguards are owed.
2. **Required** — DPIA before processing (GDPR Art. 35(3)(a)). Systematic evaluation of the customer's return history to take decisions that affect them.
3. **Required** — users must be told they are interacting with an AI system (AI Act Art. 50(1)). A clear notice at the start of the chat.
4. **Covered** — not a high-risk AI system (AI Act Annex III). Refund decisions are none of the Annex III uses; this is not creditworthiness evaluation.

Merely extra: meaningful information about the logic of the automated decision (GDPR Art. 13(2)(f)); retention of chat transcripts (GDPR Art. 5(1)(e)); security of processing (GDPR Art. 32).

Your view:

### A-007 · Automated decisions and profiling · pair of A-019

> We want to segment customers into spending-behaviour profiles (for example 'frequent traveller', 'young family') from their card transactions and use the segment to choose which of our own promotions each customer sees in the app. Nobody is refused anything; it only changes which offers are shown. Customers can turn personalised offers off in settings.

Expected: **Proceed with conditions**, medium risk, not high-risk AI, DPIA required.

1. **Covered** — no solely automated decision with a legal or similarly significant effect (GDPR Art. 22(1)). Choosing which promotions to show is profiling but not a decision that affects the customer's rights or situation, so Art. 22 does not apply.
2. **Required** — lawful basis for the profiling (GDPR Art. 6(1)(f)). Legitimate interest in marketing its own products, with a documented balancing test against the intrusiveness of transaction-based profiles; or consent.
3. **Covered** — the right to object to profiling for direct marketing is provided by the settings switch (GDPR Art. 21(2)). The switch in settings is the objection mechanism; it must be honoured at once, free of charge and brought to the customer's attention.
4. **Required** — DPIA before processing (GDPR Art. 35(1)). Profiling of financial transactions across the customer base meets two of the EDPB criteria (evaluation or scoring, large scale).

Merely extra: informing customers about the profiling in the privacy notice (GDPR Art. 13); data minimisation and data protection by design (GDPR Art. 5(1)(c), Art. 25); the AI Act not applying or the system not being high-risk.

Your view:

### A-008 · Data sharing and international transfers · pair of A-009

> We're engaging Northline Analytics, a company in Ireland, to run our monthly churn dashboards. They receive customer ids, product holdings and monthly transaction totals, host them on EU servers, process them only on our written instructions and delete everything when the contract ends; the data processing agreement is signed. Our privacy notice already names 'analytics providers' among the recipients of customer data.

Expected: **Proceed**, low risk, not high-risk AI, no DPIA.

1. **Covered** — the vendor is a processor and the contract has the required content (GDPR Art. 28(3)). Instructions, EU hosting, deletion at the end, a signed data processing agreement: the Art. 28 relationship is in place.
2. **Covered** — customers are already informed of the recipient category (GDPR Art. 13(1)(e)). The privacy notice names analytics providers among the recipients.

Merely extra: no third-country transfer, EU hosting (GDPR Art. 44); a Covered lawful-basis note (GDPR Art. 6(1)(f) or 6(1)(b)); the record of processing (GDPR Art. 30); security of processing (GDPR Art. 32); pseudonymisation of the customer ids (GDPR Art. 25).

Your view:

### A-009 · Data sharing and international transfers · pair of A-008

> Same engagement with Northline Analytics, but their standard contract says they may keep a copy of our transaction data to train and improve their own churn models, which they sell to other banks. In return we get a 30 percent discount. The data is pseudonymised with customer ids and hosted in Ireland.

Expected: **Do not build as described**, high risk, not high-risk AI, DPIA required.

1. **Blocker** — the vendor's own training is a new, incompatible purpose with no lawful basis (GDPR Art. 6(4), GDPR Art. 5(1)(b)). Selling models trained on customer transactions is not compatible with the purpose the data was collected for and the organisation has no basis to disclose it for that purpose; pseudonymised data is still personal data.
2. **Required** — for its own training the vendor is a controller, not a processor (GDPR Art. 28(10)). A processor that determines its own purposes is a controller for that processing; the processor agreement cannot cover it and the roles must be set out, if the sharing happens at all.
3. **Required** — customers must be told about a disclosure for a new purpose (GDPR Art. 13(3)). A third-party controller receiving their data for its own purposes is new information the customers have not been given.
4. **Required** — DPIA before processing (GDPR Art. 35(1)). Large-scale financial data of all customers disclosed for a new purpose to a third party.

Merely extra: pseudonymised data being personal data (GDPR Art. 4(5), Rec. 26); security of processing (GDPR Art. 32); the record of processing (GDPR Art. 30); no third-country transfer, EU hosting (GDPR Art. 44).

Your view:

### A-010 · A new AI component that is high-risk (fintech) · pair of A-011

> We want a machine-learning model to score every card transaction for fraud in real time. Transactions above the threshold are held, and an analyst in our fraud team reviews each hold within two hours and releases or confirms it; the customer is notified of a hold. The model is run for us by our US fraud-prevention vendor, which receives the transaction data and returns the score.

(The assistant's memory holds: the US fraud-prevention vendor is certified under the EU-US Data Privacy Framework (org/facts).)

Expected: **Proceed with conditions**, medium risk, not high-risk AI, DPIA required.

1. **Covered** — fraud detection is carved out of the creditworthiness high-risk item (AI Act Annex III point 5). Annex III point 5(b) excludes AI systems used for the purpose of detecting financial fraud, so this is not a high-risk AI system.
2. **Covered** — a human takes every decision on a hold (GDPR Art. 22). A hold reviewed and decided by an analyst within two hours is not a solely automated decision; the review must be real, not a rubber stamp.
3. **Required** — DPIA before processing (GDPR Art. 35(3)(a)). Systematic evaluation of every transaction of every customer.
4. **Covered** — transfer to the US vendor (GDPR Art. 45). Covered by the vendor's DPF certification, an organisation fact.
5. **Required** — the vendor is a processor and needs a contract with the Art. 28 content (GDPR Art. 28). The vendor scores the transactions on our instructions; instructions, confidentiality, sub-processors, deletion at the end.

Merely extra: a Covered lawful-basis note: fraud prevention as a legitimate interest (GDPR Art. 6(1)(f), Rec. 47) or a legal obligation (Art. 6(1)(c)); informing customers about the fraud screening (GDPR Art. 13); security of processing (GDPR Art. 32); AI literacy (AI Act Art. 4).

Your view:

### A-011 · A new AI component that is high-risk (fintech) · pair of A-010

> We licence a third-party credit-scoring model for our overdraft limit decisions. To make it work better for younger customers, our data science team wants to fine-tune the vendor's model on two years of our own customers' repayment histories and deploy the modified version under our own brand in the app. It proposes a new limit, which a credit officer approves or changes before anything is applied; customers are told the outcome and can ask for a review. Everything stays in-house.

Expected: **Proceed with conditions**, high risk, high-risk AI, DPIA required.

1. **Required** — creditworthiness evaluation is a high-risk AI system (AI Act Annex III point 5, AI Act Art. 6(2)). Overdraft limits are creditworthiness evaluation of natural persons, Annex III point 5(b); the fraud carve-out does not apply.
2. **Required** — fine-tuning and rebranding make the organisation the provider (AI Act Art. 25(1)). Putting its own name on a high-risk system, or substantially modifying it (new training data changes the weights), shifts the provider obligations to the organisation: conformity assessment, technical documentation, data governance, CE marking, not just the Art. 26 deployer duties.
3. **Required** — training on customers' repayment histories needs a basis and a compatibility test (GDPR Art. 6(4), GDPR Art. 5(1)(c)). Two years of repayment data collected for the accounts used for a new purpose: assess compatibility or a legitimate interest, and minimise or pseudonymise before training.
4. **Required** — fundamental-rights impact assessment before first use (AI Act Art. 27). A deployer of an Annex III 5(b) credit-scoring system owes a FRIA alongside the DPIA.
5. **Required** — DPIA before processing (GDPR Art. 35(3)(a)). Systematic and extensive evaluation based on profiling, with decisions that affect the customer's credit.
6. **Required** — the persons concerned must be told that a high-risk AI system is used on them (AI Act Art. 26(11)). Being told the outcome and how to appeal is not being told that a high-risk AI system evaluated them; the deployer informs them before use.
7. **Covered** — a real human decision takes it outside the solely automated prohibition (GDPR Art. 22). A credit officer approves or changes every limit and the customer can ask for a review; the officer must have the authority and competence to overturn the score.

Merely extra: meaningful information about the logic (GDPR Art. 13(2)(f)); security of processing (GDPR Art. 32); AI literacy (AI Act Art. 4); the contract with the vendor on the licence and the modification (GDPR Art. 28 does not apply, the vendor processes no data).

Your view:

### A-012 · A new AI component that is high-risk (fintech) · pair of A-016

> For account opening we want to verify identity with a selfie: the app takes a photo of the customer and matches it one-to-one against the photo on the ID document they scan. The face templates are deleted right after the match; only the yes/no result and the document scan are kept. Customers who prefer can verify by video call with an agent instead.

Expected: **Proceed with conditions**, medium risk, not high-risk AI, DPIA required.

1. **Covered** — one-to-one biometric verification is not a high-risk AI system (AI Act Annex III point 1). Annex III point 1(a) excludes AI systems used for biometric verification whose sole purpose is to confirm that a specific natural person is who they claim to be.
2. **Required** — face templates are special-category data and need an Art. 9(2) ground (GDPR Art. 9(2)(a), GDPR Art. 9(1)). Biometric data processed to uniquely identify a person; explicit consent, which the video-call alternative makes freely given.
3. **Required** — DPIA before processing (GDPR Art. 35(3)(b)). Special-category data with a new technology at onboarding.
4. **Covered** — minimisation and storage limitation are met by design (GDPR Art. 5(1)(c), GDPR Art. 5(1)(e)). The templates are deleted right after the match and only the result and the document scan are kept.

Merely extra: informing the customer about the biometric check (GDPR Art. 13); security of processing (GDPR Art. 32); the AML legal obligation as a basis for identity verification itself (GDPR Art. 6(1)(c)); AI Act Art. 50 transparency.

Your view:

### A-013 · HR and hiring · pair of A-014

> HR wants an AI tool to screen job applications: it reads CVs and cover letters, scores fit for the role, and automatically rejects the lowest-scoring half with a standard email. Recruiters only ever see the remaining half. Applicants are not told that a tool is used.

Expected: **Do not build as described**, high risk, high-risk AI, DPIA required.

1. **Blocker** — solely automated rejection with a significant effect (GDPR Art. 22(1), GDPR Art. 22(3)). Half of the applicants are rejected by the tool alone, with no human intervention and no way to contest; the pre-contract exception would still need the 22(3) safeguards.
2. **Required** — AI used for recruitment and filtering applications is a high-risk AI system (AI Act Annex III point 4, AI Act Art. 6(2)). Annex III point 4(a): recruitment or selection, filtering applications, evaluating candidates; deployer obligations apply, including human oversight by competent staff.
3. **Required** — DPIA before processing (GDPR Art. 35(3)(a)). Systematic evaluation of applicants with decisions that significantly affect them.
4. **Required** — applicants must be told about the tool and the automated decision (GDPR Art. 13(2)(f), AI Act Art. 26(11)). The existence of automated decision-making, meaningful information about the logic and the consequences; the job ad and the privacy notice say nothing today.

Merely extra: a fundamental-rights impact assessment mentioned as optional good practice (not as an obligation); national employment rules (GDPR Art. 88); AI literacy (AI Act Art. 4); security of processing (GDPR Art. 32); bias and accuracy of the tool (a provider duty, AI Act Art. 10).

Wrong if the assistant says it: a fundamental-rights impact assessment presented as an obligation (Required, AI Act Art. 27): Art. 27 reaches public bodies, private providers of public services and deployers of Annex III 5(b) and 5(c) systems only; a private fintech owes none here (false escalation).

Your view:

### A-014 · HR and hiring · pair of A-013

> Same screening tool, but it only ranks the applications and shows the score with the reasons; a recruiter reads every application, including the lowest-ranked, and decides who is invited. The job ad will say that an AI tool supports the screening, and applicants can ask for a human-only review.

Expected: **Proceed with conditions**, high risk, high-risk AI, DPIA required.

1. **Required** — ranking candidates is still a high-risk AI system (AI Act Annex III point 4, AI Act Art. 6(2)). Annex III point 4(a) covers evaluating candidates whatever the decision mode; deployer obligations: oversight by competent staff, use according to the instructions, logs.
2. **Covered** — a real human decision takes it outside the solely automated prohibition (GDPR Art. 22). The recruiter reads every application and decides, and a human-only review can be asked for; the review must be meaningful, not a rubber stamp of the ranking.
3. **Required** — DPIA before processing (GDPR Art. 35(3)(a)). Systematic evaluation of applicants on which the hiring decisions are based.
4. **Covered** — applicants are informed (GDPR Art. 13). The job ad says a tool supports the screening and offers the human-only review.

Merely extra: a fundamental-rights impact assessment mentioned as optional good practice (not as an obligation); national employment rules (GDPR Art. 88); AI literacy (AI Act Art. 4); security of processing (GDPR Art. 32); bias and accuracy of the tool (a provider duty, AI Act Art. 10).

Wrong if the assistant says it: a fundamental-rights impact assessment presented as an obligation (Required, AI Act Art. 27): Art. 27 reaches public bodies, private providers of public services and deployers of Annex III 5(b) and 5(c) systems only; a private fintech owes none here (false escalation).

Your view:

### A-015 · HR and hiring

> For our call centre we want software that allocates next week's shifts to agents from their past performance data (calls handled, customer ratings, adherence to the schedule) and flags the ten percent with the lowest scores for the monthly review. Team leads decide what to do with a flag; nobody is dismissed or disciplined by the system itself. Agents will be told in the staff handbook.

Expected: **Proceed with conditions**, high risk, high-risk AI, DPIA required.

1. **Required** — allocating tasks and evaluating workers is a high-risk AI system (AI Act Annex III point 4, AI Act Art. 6(2)). Annex III point 4(b): allocating tasks based on behaviour and monitoring and evaluating performance; deployer obligations apply: competent human oversight, use according to the instructions, logs.
2. **Required** — workers and their representatives must be informed before use (AI Act Art. 26(7)). A deployer using a high-risk system at the workplace informs the workers' representatives and the affected workers before putting it into use; a line in the staff handbook is not enough.
3. **Required** — DPIA for systematic monitoring of employees (GDPR Art. 35(3)). Systematic evaluation of employees' performance data, with effects on their work.
4. **Required** — employee data needs a basis other than consent and respect for the national employment rules (GDPR Art. 88, GDPR Art. 6(1)(f)). Employees cannot freely consent to their employer; a legitimate-interest balancing is needed, and the national rules for processing in the employment context apply.
5. **Covered** — a team lead takes every decision (GDPR Art. 22). A flag leads to a human decision in the monthly review, so Art. 22(1) does not apply; the review must be meaningful.

Merely extra: AI literacy (AI Act Art. 4); security of processing (GDPR Art. 32); bias and accuracy of the tool (a provider duty, AI Act Art. 10); a fundamental-rights impact assessment mentioned as optional good practice (not as an obligation).

Wrong if the assistant says it: a fundamental-rights impact assessment presented as an obligation (Required, AI Act Art. 27): Art. 27 reaches public bodies, private providers of public services and deployers of Annex III 5(b) and 5(c) systems only; a private fintech owes none here (false escalation); emotion recognition or a prohibited practice (AI Act Art. 5): the system reads performance figures, not emotions.

Your view:

### A-016 · Special-category data · pair of A-012

> In our branches we want cameras at the entrance that match every visitor's face against a watch-list of people who committed fraud against us in the past, and alert the branch manager in real time when there is a match. The watch-list is built from our own case files.

Expected: **Do not build as described**, high risk, high-risk AI, DPIA required.

1. **Blocker** — biometric identification of every visitor with no Art. 9(2) ground (GDPR Art. 9(1)). Face templates of everyone who walks in are biometric data processed to uniquely identify them; consent is impossible here and no law authorises a private watch-list, so the processing is prohibited.
2. **Required** — a remote biometric identification system is a high-risk AI system (AI Act Annex III point 1, AI Act Art. 6(2)). Annex III point 1(a); deployer obligations would apply to any lawful version, including registration and oversight.
3. **Blocker** — the watch-list is data relating to criminal offences (GDPR Art. 10). A list of people who committed fraud is offence-related data, which may be processed only under official authority or where Union or Member State law authorises it; a private bank cannot fulfil this by itself, so as described the watch-list is unlawful.
4. **Required** — DPIA before processing (GDPR Art. 35(3)(c)). Systematic monitoring of a publicly accessible area and special-category data on a large scale.

Merely extra: a fundamental-rights impact assessment mentioned as optional good practice (not as an obligation); signage and information at the entrance (GDPR Art. 13); security of processing (GDPR Art. 32); AI literacy (AI Act Art. 4).

Wrong if the assistant says it: a fundamental-rights impact assessment presented as an obligation (Required, AI Act Art. 27): Art. 27 reaches public bodies, private providers of public services and deployers of Annex III 5(b) and 5(c) systems only; a private fintech owes none here (false escalation).

Your view:

### A-017 · Special-category data

> Customers in financial difficulty can ask for a three-month payment holiday. To speed this up we want them to upload a doctor's note or similar proof in the app; a case handler reads it, the system stores the document, and records the type of hardship (illness, job loss, bereavement) on the customer's profile for twelve months.

Expected: **Proceed with conditions**, medium risk, not high-risk AI, DPIA required.

1. **Required** — a doctor's note and an illness flag are health data and need an Art. 9(2) ground (GDPR Art. 9(2)(a), GDPR Art. 9(1)). Explicit consent for the hardship evidence, with a route that does not require medical proof so that the consent is freely given.
2. **Required** — record less and keep it shorter (GDPR Art. 5(1)(c), GDPR Art. 5(1)(e)). Record that proof was provided rather than the diagnosis, and keep the document only as long as the decision needs it, not twelve months on the profile.
3. **Required** — DPIA before processing (GDPR Art. 35). Special-category data of customers in a vulnerable situation.
4. **Covered** — a human case handler decides (GDPR Art. 22). The decision on the payment holiday is taken by a person, so Art. 22 does not apply.

Merely extra: updating the privacy notice for the new data (GDPR Art. 13); restricted access to the documents (GDPR Art. 32); a Covered lawful-basis note for the holiday itself (GDPR Art. 6(1)(b)); the record of processing (GDPR Art. 30); the AI Act not applying.

Your view:

### A-018 · Special-category data

> Marketing wants to work out each customer's likely religion from their first and last name and the timing of their transactions (for example spending before Eid, Diwali or Christmas), store it on the marketing profile, and send holiday greetings and offers timed to the right festivals.

Expected: **Do not build as described**, high risk, not high-risk AI, DPIA required.

1. **Blocker** — inferred religion is special-category data with no ground for marketing (GDPR Art. 9(1)). Working out a customer's religion is processing data revealing religious beliefs, whether or not the guess is right; tailoring greetings and offers gives no Art. 9(2) ground, and explicit consent for this purpose is not a realistic basis.
2. **Required** — profiling for direct marketing brings the right to object (GDPR Art. 21(2)). Any lawful redesign (for example a greeting the customer opts into) must let the customer object at any time, free of charge.
3. **Required** — DPIA before processing (GDPR Art. 35(3)(b)). Special-category data across the customer base; any lawful redesign still needs one.
4. **Covered** — not a high-risk AI system (AI Act Annex III). Marketing segmentation is none of the Annex III uses and no biometric data is involved.

Merely extra: informing customers (GDPR Art. 13); purpose limitation and minimisation (GDPR Art. 5(1)(b), 5(1)(c)); security of processing (GDPR Art. 32); the lawful basis for the marketing itself (GDPR Art. 6(1)(f)).

Wrong if the assistant says it: a prohibited AI practice under AI Act Art. 5(1)(g): biometric categorisation needs biometric data, and names and dates are not biometric data.

Your view:

### A-019 · Plainly low-risk features · pair of A-007

> We want to give each customer a 'spending profile' page in the app: charts of their own transactions by category for the last twelve months, computed from data we already hold for the account. It is visible only to the customer, used for nothing else, and the categories are not stored, just computed when the page opens.

Expected: **Proceed**, low risk, not high-risk AI, no DPIA.

1. **Covered** — no automated decision and no profiling with an effect on the customer (GDPR Art. 22). A display to the customer of their own data takes no decision and evaluates nothing about them for anyone else.
2. **Covered** — lawful basis: part of the account service (GDPR Art. 6(1)(b)). Showing customers their own transactions is performance of the account contract.
3. **Covered** — data minimisation and storage limitation are met by design (GDPR Art. 5(1)(c)). Computed on the fly from data already held, nothing new stored, nothing shared.

Merely extra: a transparency note (GDPR Art. 13); security of processing (GDPR Art. 32); data protection by design (GDPR Art. 25); the AI Act not applying.

Your view:

### A-020 · Data subject rights and retention

> We're building a self-service 'Delete my account' button in the app. When a customer with a closed account, or a rejected loan applicant, taps it, the feature immediately wipes their identity data, transaction history and credit-score audit logs from all our databases, so that we comply with GDPR erasure requests instantly. Our AML policy says we keep transaction records for five years after the relationship ends, and our credit-scoring tool is a high-risk AI system whose logs we keep.

Expected: **Do not build as described**, high risk, not high-risk AI, no DPIA.

1. **Blocker** — the erasure right does not override legal retention duties (GDPR Art. 17(3)(b)). Erasure does not apply where processing is necessary to comply with a legal obligation; wiping transaction records the AML policy must keep for five years, and the credit-scoring logs, as described is unlawful.
2. **Blocker** — logs of a high-risk AI system must be kept (AI Act Art. 26(6)). A deployer keeps the logs automatically generated by a high-risk system for at least six months, or longer where Union or national law requires; deleting the credit-score audit logs on request breaks that duty.
3. **Required** — restrict instead of wipe (GDPR Art. 18). Delete what no duty requires (marketing and app profile data), restrict the retained records to the purpose of the retention duty and segregate them, and delete them when the period ends.
4. **Required** — tell the customer what is deleted and what is kept, and why (GDPR Art. 12). The response to the request says which data is erased and which is retained under which obligation.

Merely extra: security of processing (GDPR Art. 32); the record of processing (GDPR Art. 30); verifying the identity of the requester (GDPR Art. 12(6)); the one-month response time (GDPR Art. 12(3)).

Wrong if the assistant says it: treating the button as a plain erasure request to be honoured in full (Art. 17(1)) with no retention exception.

Your view:

## Anything missing?

Two or three feature descriptions a fintech product team would actually bring to a DPO that none of the twenty
cases covers, with the answer you would expect, would be the most valuable addition.

Your view:
