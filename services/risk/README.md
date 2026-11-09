# Risk

Experimental long-only paper position sizing.

The calculator uses `Decimal` and the formula:

```text
shares = floor(min(
  account equity × risk fraction / stop distance,
  account equity × max allocation / entry price
))
```

Example defaults are 0.5% planned equity risk per trade, a 1% daily loss stop, a 3% weekly stop, and a 10% position allocation. The absolute code ceiling rejects a risk fraction above 0.02. Daily and weekly stops are stored on the policy and are not enforced against a ledger.

`size_position` calculates only. It cannot submit an order, open a short, or permit execution.

This is not investment advice. Stops can fail.
