# To the Architect: where should kitchen and billing policy live?

Question: how do we prevent query order and repeated relative labels from changing
money or plate totals?

Architect response: resolve each source event's calendar day against its own
timestamp and replay copied events once per day. Both projections must call that
same replay with identical cutoff and acceptance options. Return annotations on
copies; never annotate the input list. Keep payment authorization at the ledger
boundary, independent of any extraction or UI caller. Session confirmations are
not model fields, and a newly loaded chat invalidates them.

Repository evidence: the old `_final_states` reset its day map for every event and
keyed by the spoken label; the sheet annotated the shared event objects. The
repaired `_replay_day`, `_final_states`, and `plates_by_day` share daily state.
The property suite and the ten-evening regression exercise the disputed invariant.

Opening-balance CSV is a replace operation. Reimporting the same file cannot add
the opening balance twice. It does not establish a bank reconciliation or durable
accounting database. Alias merges require confirmation because a prefix is only
a suggestion about identity.
