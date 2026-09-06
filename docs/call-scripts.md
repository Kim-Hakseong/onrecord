# Counterpart call scripts

Printed and read aloud by the person answering. These are the failure modes the product is
built for, so they are rehearsed rather than hoped for.

**These are re-enactments.** The counterparts are the builder's own second number and one
acquaintance. Nobody in these calls is a real supplier or a real employment reference, and
this is stated in the video subtitles and the README.

**Answer in English.** The reviewers are English-speaking, and a demo whose evidence they
cannot read cannot demonstrate that the highlighted quote is really in the transcript — which
is the entire claim. Script E is the one exception and exists to show the rules do not depend
on the language.

## A — evasive answer (expects: date UNRESOLVED, reason CONFIRMED)

Answer as the sales rep. Identify yourself once, clearly:

> Sure, this is Min-su Kim, I handle sales here.

When asked for the ship date, do **not** give one. Hedge, and offer to call back:

> Hmm, it should go out sometime this month I think, but let me check and get back to you.

When asked why it slipped, answer plainly — this field should settle:

> We're waiting on material from our own supplier.

Do not volunteer a quantity. If pushed for a date a second time, repeat the hedge.

## B — stand-in with no authority (expects: date NO_AUTHORITY, reason CONFIRMED)

Answer as an assistant, and say so:

> I'm the office assistant. He's out on site today.

Then give a **clear, specific** date — this is the point of the scenario. The value is
unambiguous and still must not settle:

> It says here it ships on September 25th.

Reason, also from the record:

> It says production line delay.

## C — no answer (expects: every field UNRESOLVED, end_reason recorded)

Do not pick up. Let it reach voicemail. Nothing else to do.

## D — follow-up, shortened (expects: three fields CONFIRMED)

Answer as the sales rep again. Answer each question directly and briefly; the call should be
audibly shorter than call A.

> Yes, Min-su Kim from sales. I checked on it.
> It ships on September 24th.
> All 500 units.
> Yes, that's possible.

## E — contradiction (expects: date CONTRADICTED against the ERP's 2026-09-20)

Answer as the account manager:

> Yes, this is Su-jin Lee, I manage this account.
> We can ship on October 2nd. Anything earlier isn't going to happen.
> 300 units.
> Raw material deliveries are running late.

## F — the same call in Korean (expects: identical verdicts)

One call only, to show the adjudicator does not read the language. Answer as the sales rep:

> 네, 영업 담당 김민수입니다.
> 9월 24일에 출고됩니다.
> 500개 전량 나갑니다.

## Rules for whoever is answering

- Say your role out loud, once, in a full sentence. The adjudicator will not accept a role it
  cannot quote, so a mumbled or implied role means every field lands on NO_AUTHORITY.
- Say dates the way a person would (`September 24th`, `9월 24일`), not in ISO. Normalising them
  is the parser's job and it should be exercised.
- Do not help. If the script says hedge, hedge — including when the agent asks a third time.
- One answer per question. Do not pre-empt questions that were not asked; the goal shrinking
  is only visible if the follow-up call is genuinely shorter.
