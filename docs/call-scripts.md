# Counterpart call scripts

Printed and read aloud by the person answering. These are the failure modes the product is
built for, so they are rehearsed rather than hoped for.

**These are re-enactments.** The counterparts are the builder's own second number and one
acquaintance. Nobody in these calls is a real supplier or a real employment reference, and
this is stated in the video subtitles and the README.

## A — evasive answer (expects: date UNRESOLVED, reason CONFIRMED)

Answer as the sales rep. Identify yourself once, clearly:

> 네, 영업 담당 김민수입니다.

When asked for the ship date, do **not** give one. Hedge, and offer to call back:

> 음... 아마 이번 달 안에는 나갈 것 같은데요, 확인해보고 다시 연락드릴게요.

When asked why it slipped, answer plainly — this field should settle:

> 자재 수급이 늦어져서 그렇습니다.

Do not volunteer a quantity. If pushed for a date a second time, repeat the hedge.

## B — stand-in with no authority (expects: date NO_AUTHORITY, reason CONFIRMED)

Answer as an assistant, and say so:

> 저는 사무 보조입니다. 담당자분은 오늘 외근 나가셨어요.

Then give a **clear, specific** date — this is the point of the scenario. The value is
unambiguous and still must not settle:

> 9월 25일에 출고된다고 적혀 있네요.

Reason, also from the record:

> 생산 라인 지연 때문이라고 되어 있습니다.

## C — no answer (expects: every field UNRESOLVED, end_reason recorded)

Do not pick up. Let it reach voicemail. Nothing else to do.

## D — follow-up, shortened (expects: three fields CONFIRMED)

Answer as the sales rep again. Answer each question directly and briefly; the call should be
audibly shorter than call A.

> 네, 영업 담당 김민수입니다. 확인했습니다.
> 9월 24일에 출고됩니다.
> 500개 전량 나갑니다.
> 네, 가능합니다.

## E — contradiction (expects: date CONTRADICTED against the ERP's 2026-09-20)

Answer as the account manager:

> 네, 거래처 관리 담당 이수진입니다.
> 10월 2일에 출고 가능합니다. 그 전에는 어렵습니다.
> 300개 나갑니다.
> 원자재 입고가 지연되고 있습니다.

## Rules for whoever is answering

- Say your role out loud, once, in a full sentence. The adjudicator will not accept a role it
  cannot quote, so a mumbled or implied role means every field lands on NO_AUTHORITY.
- Say dates the way a person would (`9월 24일`), not in ISO. Normalising them is the parser's
  job and it should be exercised.
- Do not help. If the script says hedge, hedge — including when the agent asks a third time.
- One answer per question. Do not pre-empt questions that were not asked; the goal shrinking
  is only visible if the follow-up call is genuinely shorter.
