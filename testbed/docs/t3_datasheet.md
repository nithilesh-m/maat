# ACSIncome classifier: datasheet

## Intended purpose
Pre-screening of loan applicants in a research testbed. Not for production credit decisions.

## System description
A gradient-boosted tree classifier predicting whether annual personal income exceeds 50,000 USD. Architecture overview: scikit-learn HistGradientBoostingClassifier on five tabular features.

## Training data and data sources
Training data: American Community Survey (ACS) PUMS 2018, California, via the folktables package. Data sources are public domain US Census records.

## Data governance
Data governance: public data only, no personal identifiers. Provenance and lineage: folktables ACSIncome task, filtered to adults with positive hours and income.

## Performance metrics
Accuracy and group-wise selection rates are evaluated on a held-out California split.

## Limitations
Limitations: the model reflects 2018 California income patterns and may not transfer to other states or years. Known issue: income labels encode historic pay gaps.

## Risk management
Risk assessment and monitoring of group fairness and drift are required before any use.

## Human oversight
Human oversight: a credit officer reviews every decision; the model only pre-screens.

## Logging
Logging: predictions and inputs are recorded for audit (audit log).

## Ethical considerations
Fairness: sex and race are sensitive attributes and are monitored for demographic parity and equalized odds.
