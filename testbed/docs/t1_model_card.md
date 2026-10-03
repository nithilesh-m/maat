# ExampleShop billing assistant: model card

## Intended purpose
Answers billing questions for retail customers of ExampleShop. It is not intended for legal, medical or credit decisions.

## System description
A retrieval-augmented chatbot: BM25 retrieval over the billing FAQ, a local open-weight language model generates the answer and cites the passages used. Architecture overview: portal front end, retrieval service, model server.

## Training data and data sources
The model is a pre-trained open-weight model, not fine-tuned. The retrieval dataset is the public billing FAQ (six documents). Data sources and provenance: written by the support team, reviewed quarterly.

## Data governance
Data governance: no customer personal data is placed in the retrieval corpus. Lineage of each document is tracked in the support wiki.

## Performance metrics
Evaluation on a 12-question billing QA set: accuracy and answer faithfulness are tracked per release.

## Limitations and known issues
Limitations: the assistant can be wrong about edge cases, answers in English only, and does not see the customer's account.

## Risk management
Risk assessment is reviewed each release. Identified risks: prompt injection, personal data leakage, outdated policy text.

## Human oversight
Human oversight: support agents review flagged conversations daily and can override any answer.

## Logging
Logging and record-keeping: all conversations are logged with timestamps for 12 months (audit log).

## Post-market monitoring
Post-market monitoring plan: weekly review of complaint rates and escalation rates.

## Ethical considerations
Fairness: decisions about fee waivers must not depend on a customer's nationality, gender or age.
