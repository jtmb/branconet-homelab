# RULES.md — authoritative working rules

This file is the **authoritative** source for how agents work in this
repository. `AGENTS.md` and every skill under `.agents/skills/` defer to it.
If another document disagrees with a rule here, this file wins; fix the other
document. Only James can change or remove a rule here.

## Rule 1 — Agents own routine testing

Agents own routine testing. Use the agent browser in OpenCode to sign in,
exercise pages, and check what appears on screen. Use the available network or
cluster tools for checks a browser can't answer. Report what you verified in
plain language, with a screenshot or simple diagram when it helps. Reuse valid
evidence. Don't ask James to repeat a test the agent can perform. Involve him
only when the remaining step genuinely requires his access, action, or
judgment.

What this means in practice:

| Situation | Who does it |
|---|---|
| Open a page, sign in, click through, read what is shown | Agent (agent browser) |
| Check a certificate, DNS answer, port, service or cluster object | Agent (shell, kubectl, Ansible, MCP tools) |
| A test already passed and nothing it depends on changed | Reuse the result; don't redo it or ask James to |
| A password, physical device, or decision only James has | Ask James, once, saying exactly what is needed |

Record agent-performed checks as "verified by the agent", not as if James
personally saw them.

## Rule 2 — Plain language for James

When explaining a plan or result to James, use common language rather than
jargon, say what will be done and what he will notice, give each item a clear
"done when", and use a simple table or diagram when it helps.
