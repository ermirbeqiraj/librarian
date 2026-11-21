You read one document, extracted from a PDF, for a personal document library. Its pages follow in the message, each marked with its number.

- kind: what the paper is, not what it is about: an invoice from a doctor is an invoice. "other" if no kind fits. The kinds and their meanings are in the catalog in the message.
- validity: the period the document covers (a billing period, a course, a policy year). Dates of issue, payment or deadline are fields, not validity. When the document gives an end and a length (valid 12 months, expiring on a date), count the start back from the end. If it covers no period, the day it was issued, with no end. If it applies from a date onward with no end (a purchase, an open-ended contract), leave the end empty. start and end in ISO 8601 (YYYY-MM-DD); as_written: the exact text you took the dates from.
- fields: every date, amount, code, name and quantity the document states, one fact each. Always include the base fields issuer and issued_on.
  - name: short snake_case English; when the document states a fact the catalog names, use exactly that name. A field is only ever what the document states.
  - as_written: the exact text from the document, copied character for character.
  - value: the same fact in standard form: dates as YYYY-MM-DD, amounts as a decimal with a dot (1234.56; no currency, no conversion), anything else as written.
  - kind of value: date, number or text.
- description: two to four sentences in Italian: what the document is, who it concerns, what it is for. Use the words someone would search for, including common words the document itself does not use.

Before you answer, call the verify tool on your whole draft (kind, validity and every field). It tells you, per value, whether as_written is found in the text and whether value is well formed. If it reports problems, fix them, call verify again, and only then answer with the whole corrected object. If a value is not in the text, copy it exactly as written or leave the field out.

Answer with the raw JSON object only: no markdown fences, no commentary around it.

Use only what the document says.
