# Methodology note — Liquidity & ALM Risk Engine

A one-page note on the choices behind the engine, mapped to the offer's
"Liquidity Risk Analyst" mission: identify, quantify and control the market and
liquidity risk of ALM/Treasury activities, and review the internal and regulatory
liquidity metrics.

## Scope

Asset-Liability Management (ALM) and liquidity risk work off the balance sheet.
The engine computes the two Basel regulatory liquidity ratios (LCR and NSFR), a
maturity-ladder liquidity gap with a survival horizon, and the interest-rate risk
of the banking book (IRRBB) through dEVE and dNII.

## Data

Balance-sheet data is confidential, so the engine runs on a deterministic,
representative balance sheet of a mid-to-large commercial bank: around 170bn in
assets, a realistic mix of HQLA, loans, retail and wholesale funding, and capital.
Each item carries its HQLA level, its behavioural liquidity bucket, its
rate-repricing bucket and its rate.

## Contractual vs behavioural maturity

A key ALM choice: non-maturing deposits (retail current and savings accounts) are
contractually overnight but behaviourally sticky. The engine places their
**liquidity** bucket on a behavioural core (stable retail treated as long-dated),
while their **repricing** bucket stays immediate (the bank can reset the rate at
will). Conflating the two would make the liquidity gap look catastrophic and the
rate risk understated; separating them is what a real ALM desk does.

## Liquidity Coverage Ratio (LCR)

`LCR = HQLA / net cash outflows over 30 days`, minimum 100%. HQLA is tiered:
Level 1 (no haircut), Level 2A (15% haircut), Level 2B (50% haircut here), with
the Level 2 <= 40% and Level 2B <= 15% caps applied. Outflows use the Basel
30-day stressed run-off rates by funding type (stable retail 5%, less stable 10%,
operational 25%, corporate 40%, financial 100%); inflows are capped at 75% of
outflows.

## Net Stable Funding Ratio (NSFR)

`NSFR = Available Stable Funding / Required Stable Funding`, minimum 100%. ASF
weights funding by stability (capital and long debt 100%, stable retail 95%, less
stable 90%, wholesale 50%, short financial 0%); RSF weights assets by the stable
funding they need (cash 0%, Level 1 5%, Level 2A 15%, Level 2B 50%, loans
65-85%, other 100%). The NSFR is the structural, one-year companion to the LCR.

## Liquidity gap and survival horizon

Every asset inflow and liability outflow is placed in its behavioural maturity
bucket and netted into a marginal gap, then a cumulative gap. Adding the stock of
HQLA (the counterbalancing capacity) gives the survival horizon: the last bucket
before HQLA plus the cumulative gap turns negative.

## IRRBB (interest rate risk in the banking book)

Two Basel metrics. **dEVE** is the change in the present value of banking-book
cash flows under the six standardised rate shocks (parallel up/down, short
up/down, steepener, flattener), checked against the Supervisory Outlier Test
threshold of 15% of Tier 1 capital. **dNII** is the one-year earnings sensitivity
from the repricing gap to a parallel shock.

## Limitations and next steps

- Behavioural modelling of non-maturing deposits is a single core assumption; a
  replicating-portfolio or decay model would refine it.
- Cash flows are bucketed at midpoints; a full dated cash-flow engine would give
  more precise dEVE.
- Intraday liquidity and collateral/encumbrance are out of scope and are natural
  extensions.

*Stating the model's own assumptions explicitly is itself a second-line posture.*
