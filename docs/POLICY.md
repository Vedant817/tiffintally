# Kitchen and billing policy

The sheet and bill replay the same daily state. Event dates resolve against each
message's timestamp; an undated or invalid date is withheld. A message in the
small hours uses the preceding evening for relative words and is shown for review.

New and change replace the count; add increments it. A later restatement applies
and is shown to the cook. Contradictory counts in the same minute are withheld.
Cancels and pauses clear the corresponding day and meal. A dated pause range
clears only days in that range. Later explicit orders resume that day.

With a cutoff configured, late orders stay pending. Late cancels stay pending
until the cook accepts them. The ledger uses the same cutoff and acceptance state
as the sheet. Direct library callers can omit a cutoff deliberately.

`qty` is the total plates requested for each indicated meal. A named secondary
customer receives `secondary_qty` of that total (default one); the sender receives
the remainder. An impossible allocation is withheld. Alias suggestions require
the cook's confirmation; first names alone never merge customers automatically.

Amounts are rounded to paise using Decimal. The session's price applies to the
loaded chat; it is not a historical price book. Opening balances are imported and
closing balances exported as customer,balance CSV. Import replaces opening
balances, so repeated imports do not add money twice. Payments from chat are
claims, not receipts; only eligible payments explicitly confirmed by the cook
reduce dues. Review or audit flags cannot be overridden by payment confirmation.
