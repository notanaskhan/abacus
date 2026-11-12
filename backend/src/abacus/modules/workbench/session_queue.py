"""The session's side queue (P-10-T43; SPEC-647 AC-S2), pure so the workflow replays it.

A session holds one open question at most. Messages and answers queue in arrival order:

- A message typed while a question is open is a turn of its own, taken in turn. It is answered
  without waiting for the question, and the question stays open (the side queue).
- An answer is taken for the question it names. It closes that question; an answer to a
  question that is no longer open (answered already, or replaced) is dropped as stale.
- A turn that asks a new question replaces the open one.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

WorkKind = Literal["message", "answer"]


@dataclass(frozen=True)
class SessionWork:
    kind: WorkKind
    seq: int  # the item's seq: a message's own, an answer's own
    question_seq: int = 0  # an answer: the question item it answers


@dataclass
class SessionQueue:
    pending: deque[SessionWork] = field(default_factory=deque[SessionWork])
    open_question: int = 0  # the open question item's seq, 0 when none

    def message(self, seq: int) -> None:
        self.pending.append(SessionWork("message", seq))

    def answer(self, seq: int, question_seq: int) -> None:
        self.pending.append(SessionWork("answer", seq, question_seq))

    def take(self) -> SessionWork | None:
        """The next turn to run, skipping stale answers; None when nothing waits."""
        while self.pending:
            work = self.pending.popleft()
            if work.kind == "answer" and work.question_seq != self.open_question:
                continue
            return work
        return None

    def turn_ended(self, work: SessionWork, asked: int) -> None:
        """After a turn: an answer closes its question; a turn that asked opens its own."""
        if work.kind == "answer":
            self.open_question = 0
        if asked:
            self.open_question = asked

    def snapshot(self) -> tuple[list[SessionWork], int]:
        """For continue-as-new: what waits, and the open question."""
        return list(self.pending), self.open_question

    @classmethod
    def resume(cls, pending: list[SessionWork], open_question: int) -> SessionQueue:
        return cls(deque(pending), open_question)
