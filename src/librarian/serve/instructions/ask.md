Ask the library one question, in Italian. One question per call, and it stands alone: include
what the conversation settled (the period, the provider, the person). Returns `status`, `values`
(one fact each), `passages` (the documents' own text that backs them), `sources` (where each
comes from: `document_id`, `section_id`, their sizes in characters, and `file`, a link to the
original or null) and `trace_id`. It can take a minute or more.
