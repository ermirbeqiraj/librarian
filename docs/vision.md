# Vision

A household's paper ends up as a folder of PDFs: bills, receipts, contracts, statements. Paying
them is mostly automatic; understanding them is not. What they say over time, and what the small
print commits you to, stays buried because nobody reads a hundred PDFs side by side.

The Librarian reads every document dropped in a folder, works out what it is, and keeps what it
says: its kind, the period it covers, its key fields, and its text in sections. Then it answers
the questions that need all of them at once.

## How you reach it

The Librarian is not an app you open. You talk to your own AI assistant (Claude, Mistral Vibe,
or whichever you use) and the assistant asks the Librarian. It is exposed as an MCP server: the
assistant calls `ask` with a question in plain language, reads further with `get_section` and
`get_document`, and rates an answer with `feedback`. The assistant stays the conversation; the
Librarian stays the one that knows the documents.

## How it stays out of the way

It is meant to sit hidden and run for years without becoming a job. So it carries as little as
it can:

- **No user interface, no accounts.** The assistant is the interface.
- **No auth of its own to maintain.** On a server it sits behind Cloudflare Access, which logs
  the caller in; the Librarian only checks the token Access signs. A bearer token covers a
  machine with no Access in front.
- **One container and a folder.** Documents go in the inbox, and are filed away by themselves.
  The image migrates its database on start, and every push to `main` publishes a new one.
- **Nothing to tend between documents.** A document it can't read goes to quarantine with the
  reason, instead of stopping the rest.

## Where it shines

- **Trends.** How consumption and spending move across months and years, for one service or
  all of them: "has the electricity gone up since the new tariff?", "what did water cost per
  year, and why did one year jump?". The fields are structured, so the numbers come from the
  documents, not from a model's arithmetic.
- **Reminders.** Dates that matter and are easy to miss: an offer's price ending, a contract
  that renews unless cancelled, a notice period, a warranty running out. They sit in documents
  that were filed and forgotten.
- **Side clauses.** The conditions in the small print: what a contract allows the other side to
  change, what a cancellation costs, what an offer excludes. The text is kept whole, section by
  section, so the agent can find the clause and quote it.

## Two promises

- **It says where an answer comes from.** Every value points at its source and every claim at
  its passage. A value read by code that knows the document's layout is marked verified; one a
  model drafted is not.
- **It knows what it doesn't know.** When the documents don't hold the answer, it says so
  instead of guessing.

## How it grows

One document kind at a time. A layout read often gets a parser, written and tested against real
copies, and its documents become confirmed; anything else is still read by a model and kept as
a draft. Questions grow the same way: each kind of question the agent gets wrong becomes a case
in an eval before the fix, so a change is measured, not believed. The ratings an assistant sends
back point at the answers to look at first.

Reminders come the same way: through the assistant, when it asks, until the Librarian can tell
it on its own.
