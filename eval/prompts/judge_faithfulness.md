You measure the faithfulness of a GDPR / EU AI Act compliance assistant's text to the material it was given:
the legal passages it retrieved and, when provided, the organisation's memory items it read. Faithfulness here
means "stays within that material", not "is legally correct": a true statement that the material does not
support is still unsupported.

## Step 1: statements

Split the text into self-contained statements. Rules:

- Each statement must stand alone: resolve pronouns and references ("it", "this requirement") into the thing
  they refer to.
- Keep a legal rule and its condition or exception together in ONE statement: clauses introduced by "if",
  "unless", "provided that", "except", "where" stay with the rule they qualify. Never split "processing is
  prohibited under Art. 9(1) unless an Art. 9(2) condition applies" into two statements, which would turn a
  faithful conditional into an unfaithful absolute.
- A citation is a statement of its own. "Under Art. 5(1)(c) data must be minimised" gives two statements: the
  proposition ("personal data must be limited to what is necessary for the purpose") and the citation claim
  ("GDPR Art. 5(1)(c) is the provision that says personal data must be limited to what is necessary").
- Label each statement with its kind: "proposition" (a claim about what the law requires, permits or
  prohibits, applied to the feature or in general), "citation" (that a named provision says a given thing),
  "restates_input" (it only repeats what the feature description or the question said, e.g. "the feature shares
  scores with a US vendor"), or "not_factual" (a recommendation, a next step, a disclaimer, a heading).
- A recommendation is an action the assistant tells the team to take in order to comply, where the action
  itself is not what the law states: "document the lawful basis before deployment", "specify a retention
  period", "justify device data separately", "set up a process for explanations". These are "not_factual",
  even when written as "must": the law requires the lawful basis, the storage limit or the explanation, not
  the documenting, the deadline or the process. Only the legal rule inside such a sentence is a proposition;
  split it out ("processing needs a lawful basis under Art. 6(1)") and leave the action as not_factual.

Example. Text: "Fully automated rejections are prohibited unless the customer can obtain human intervention
(GDPR Art. 22(3)). The feature shares scores with a US vendor; that transfer is covered by the vendor's DPF
certification (GDPR Art. 45)."
Statements:
1. proposition: a decision based solely on automated processing is prohibited unless the data subject can obtain human intervention
2. citation: GDPR Art. 22(3) is the provision that gives the data subject the right to obtain human intervention
3. restates_input: the feature shares scores with a US vendor
4. proposition: the transfer of scores to the US vendor is covered by the vendor's Data Privacy Framework certification
5. citation: GDPR Art. 45 is the provision under which a transfer may rely on an adequacy decision

## Step 2: verdicts

For each statement of kind "proposition" or "citation", first write the reason, then the verdict:

- "supported": the material (a passage, or a memory item) states it or entails it. Entailment includes
  applying a general rule to the feature's specific data: the law speaks of "personal data", so "device
  fingerprint data must be limited to what is necessary" is supported by Art. 5(1)(c) although no passage
  mentions device fingerprints; "the vendor transfer is covered by the DPF certification" is supported by
  Art. 45 together with the memory item that states the certification. Do not require the material to name
  the feature's data, vendor or product. For a citation statement, the passage carrying that label must say
  what the statement attributes to it; a passage with another label saying the same thing does NOT support a
  citation statement.
- "not_supported": the material does not say it, says something different, or the cited provision says
  something else.
- "not_factual": on reflection the statement is not a checkable claim.

Statements of kind "restates_input" and "not_factual" get the verdict "not_factual" without a check.

Example, with the material containing the text of GDPR Art. 22 and a memory item "the US fraud-prevention
vendor is certified under the EU-US Data Privacy Framework (org/facts)":
1. reason: Art. 22(1) and (3) in the material state the prohibition and the right to human intervention. verdict: supported
   (had the statement been "the exception must be documented before deployment", it would have been a
   recommendation in step 1, not a proposition, and would not be checked)
2. reason: the passage labelled GDPR Art. 22(3) contains "the right to obtain human intervention". verdict: supported
4. reason: the memory item states the vendor's DPF certification; Art. 45 in the material makes an adequacy decision a basis for transfer. verdict: supported
5. reason: the passage labelled GDPR Art. 45 says a transfer may take place where the Commission has decided the country ensures an adequate level of protection. verdict: supported
